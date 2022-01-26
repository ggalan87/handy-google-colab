import sys
import subprocess
from pathlib import Path
import json
import shutil
from google.colab import drive
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_ssh_public_key


def update_os():
    subprocess.run(['apt', '-qq', 'update'])


def restart_system_service(service_name: str):
    subprocess.run(['service', service_name, 'restart'])


def install_os_package(package_name: str):
    subprocess.run(['apt', '-qq', 'install', '-y', package_name])


def install_python_package(package_name: str):
    subprocess.run([sys.executable, '-m', 'pip', '-q', 'install', package_name])


def write_content_to_file(filepath: Path, content: str):
    with filepath.open('w') as f:
        f.write(content)


def setup_ssh(tunnel_options_path: Path) -> Path:
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
    restart_system_service('ssh')

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
    for p in tunnel_options_path.iterdir():
        if public_key_text is None:
            public_key_text, public_key_path = check_load_public_key(p)
        if private_key_text is None:
            private_key_text, private_key_path = check_load_private_key(p)

    if public_key_text is None or private_key_text is None:
        raise RuntimeError(f'Public/private keys not found or malformed.')

    authorized_keys_path = ssh_path / 'authorized_keys'
    write_content_to_file(authorized_keys_path, public_key_text)
    authorized_keys_path.chmod(0o600)

    private_key_pem = ssh_path / 'private_key.pem'
    write_content_to_file(private_key_pem, private_key_text)
    private_key_pem.chmod(0o600)

    return private_key_path


def setup_environment(gdrive_folder: str):
    # Mount google drive folder
    drive.mount('/content/drive')

    tunnel_options_path = Path(gdrive_folder)

    if not tunnel_options_path.exists():
        raise RuntimeError(f'Specified tunnel options path does not exist {tunnel_options_path}')

    config_file_path = tunnel_options_path / 'config.json'
    if not config_file_path.exists():
        raise RuntimeError(f'Config file does not exist {config_file_path}')

    with open(config_file_path, 'r') as f:
        config = json.load(f)

    # Install mandatory packages
    update_os()
    install_os_package('openssh-server')

    # Install extra packages
    for p in config['python_packages']:
        install_python_package(p)

    for p in config['os_packages']:
        install_os_package(p)

    private_key_path = setup_ssh(tunnel_options_path)

    return config['tunnel_options']['service_url'], config['tunnel_options']['service_port'], \
           config['tunnel_options']['local_port'], private_key_path.name


def start_tunnel(gdrive_folder: str):
    service_url, service_port, local_port, private_key_name = setup_environment(gdrive_folder)

    # print a message on how to connect
    local_cmd = f'ssh -oStrictHostKeyChecking=no -oUserKnownHostsFile=/dev/null -i {private_key_name} -p ' \
                f'{service_port} -L {local_port}:localhost:{local_port} root@{service_url}'

    print(f'Tunnel will run now. Use the following command to connect:\n{local_cmd}\n'
          f'\nPut the correct location of the private key if not run in the same folder.')

    # ssh tunnel start
    subprocess.run([
        'ssh',
        '-oStrictHostKeyChecking=no',
        '-oUserKnownHostsFile=/dev/null',
        '-i', '/root/.ssh/private_key.pem',
        '-f', '-R', f'{service_port}:localhost:22',
        f'{service_url}', '-N'
    ])
