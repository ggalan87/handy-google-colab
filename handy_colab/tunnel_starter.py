import sys
import subprocess
from pathlib import Path
import json
import configparser
from abc import abstractmethod
from collections import namedtuple
import shlex
import requests
import tarfile
import io
import shutil
from typing import Optional
from google.colab import drive
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_ssh_public_key


class GenericTunnel:
    def __init__(self, gdrive_folder: str):
        self._setup_environment(gdrive_folder)

    def _setup_environment(self, gdrive_folder: str):
        # Mount google drive folder
        drive.mount('/content/drive')

        self._tunnel_options_path = Path(gdrive_folder)

        if not self._tunnel_options_path.exists():
            raise RuntimeError(f'Specified tunnel options path does not exist {self._tunnel_options_path}')

        config_file_path = self._tunnel_options_path / 'user_config.json'
        if not config_file_path.exists():
            raise RuntimeError(f'Config file does not exist {config_file_path}')

        with open(config_file_path, 'r') as f:
            config = json.load(f)

        # Install mandatory packages
        self.update_os()
        self.install_os_package('openssh-server')

        # Install extra packages
        for p in config['python_packages']:
            self.install_python_package(p)

        for p in config['os_packages']:
            self.install_os_package(p)

        self._private_key_path = self._setup_ssh()
        self._service_url = config['tunnel_options']['service_url']
        self._service_port = config['tunnel_options']['service_port']
        self._local_port = config['tunnel_options']['local_port']

    def _setup_ssh(self) -> Path:
        def check_load_public_key(path: Path):
            try:
                pub = load_ssh_public_key(path.open('rb').read())
                pub_text = pub.public_bytes(encoding=serialization.Encoding.OpenSSH,
                                            format=serialization.PublicFormat.OpenSSH).decode()
                return pub_text, path
            except (ValueError, Exception):
                return None, None

        def check_load_private_key(path: Path):
            try:
                priv = load_pem_private_key(path.open('rb').read(), password=None)

                priv_text = priv.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode()
                return priv_text, path
            except (ValueError, Exception):
                return None, None

        config_path = Path(__file__).parent / 'config'

        # Copy sshd config to the standard directory
        shutil.copyfile(config_path / 'sshd_config', '/etc/ssh/sshd_config')

        # Restart sshd
        self.restart_system_service('ssh')

        env_exports_path = config_path / 'env_exports'
        bashrc_path = Path('/root/.bashrc')

        with bashrc_path.open('a') as tf:
            with env_exports_path.open('r') as sf:
                tf.write(sf.read())

        ssh_path = Path('/root/.ssh')
        ssh_path.mkdir(exist_ok=True)
        ssh_path.chmod(0o700)

        public_key_text, public_key_path = None, None
        private_key_text, private_key_path = None, None

        # Check which file in the folder is pub/priv key
        for p in self._tunnel_options_path.iterdir():
            if public_key_text is None:
                public_key_text, public_key_path = check_load_public_key(p)
            if private_key_text is None:
                private_key_text, private_key_path = check_load_private_key(p)

        if public_key_text is None or private_key_text is None:
            raise RuntimeError(f'Public/private keys not found or malformed.')

        authorized_keys_path = ssh_path / 'authorized_keys'
        self.write_content_to_file(authorized_keys_path, public_key_text)
        authorized_keys_path.chmod(0o600)

        private_key_pem = ssh_path / 'private_key.pem'
        self.write_content_to_file(private_key_pem, private_key_text)
        private_key_pem.chmod(0o600)

        return private_key_path

    @staticmethod
    def run_raw(cmd: str):
        subprocess.run(shlex.split(cmd))

    @staticmethod
    def update_os():
        subprocess.run(['apt', '-qq', 'update'])

    @staticmethod
    def restart_system_service(service_name: str):
        subprocess.run(['service', service_name, 'restart'])

    @staticmethod
    def install_os_package(package_name: str):
        subprocess.run(['apt', '-qq', 'install', '-y', package_name])

    @staticmethod
    def install_python_package(package_name: str):
        subprocess.run([sys.executable, '-m', 'pip', '-q', 'install', package_name])

    @staticmethod
    def write_content_to_file(filepath: Path, content: str):
        with filepath.open('w') as f:
            f.write(content)

    @abstractmethod
    def start_tunnel(self):
        pass


class PortmapTunnel(GenericTunnel):
    def start_tunnel(self):
        private_key_name = self._private_key_path.name

        # print a message on how to connect
        local_cmd = f'ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i {private_key_name} -p ' \
                    f'{self._service_port} -L {self._local_port}:localhost:{self._local_port} root@{self._service_url}'

        print(f'Tunnel will run now. Use the following command to connect:\n{local_cmd}\n'
              f'\nPut the correct location of the private key if not run in the same folder.')

        # obtain the username from the name of th key, which is the filename except .pem
        service_username = private_key_name.rsplit('.', 1)[0]

        cmd = f'ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i /root/.ssh/private_key.pem -f -R' \
              f' {self._service_port}:localhost:22 {service_username}@{self._service_url} -N'

        # ssh tunnel start (in background)
        # TODO: Use something more robust for monitoring, such as https://gist.github.com/carlohamalainen/3803816
        self.run_raw(cmd)


class FRPTunnel(GenericTunnel):
    def _setup_environment(self, gdrive_folder: str):
        super()._setup_environment(gdrive_folder)

        frp_path = self.download_frp('/root')

        if frp_path is None:
            return

        # Setup frpc.ini from existing config options
        self._frpc_ini_path = frp_path / 'frpc.ini'
        config = configparser.ConfigParser()
        config.read(self._frpc_ini_path)
        config.set('common', 'server_addr', self._service_url)
        config.set('common', 'server_port', self._service_port)
        # kind of misleading but by local_port I mean the port local to the colab machine that accepts remote connection
        config.set('ssh', 'remote_port', self._local_port)

        with open(self._frpc_ini_path, 'w') as configfile:
            config.write(configfile)

    def start_tunnel(self):
        cmd = f'./frp/frpc -c {self._frpc_ini_path}'
        self.run_raw(cmd)

    def download_frp(self, output_path) -> Optional[Path]:
        frp_releases_url = 'https://api.github.com/repos/fatedier/frp/releases/latest'
        response = requests.get(frp_releases_url)
        data = json.loads(response.text)
        latest_release_url = None
        for asset in data['assets']:
            if 'linux_amd64' in asset['name']:
                latest_release_url = asset['browser_download_url']

        download_path = Path(output_path)
        frp_path = download_path / 'frp'

        # Cleanup existing
        shutil.rmtree(frp_path, ignore_errors=True)

        if latest_release_url is None:
            return None

        response = requests.get(latest_release_url)
        frp_file = tarfile.open(fileobj=io.BytesIO(response.content), mode="r|gz")
        frp_file.extractall(download_path)

        # Rename to simply frp
        for p in download_path.iterdir():
            if 'frp' in p.name:
                p.rename('frp')

        return frp_path
