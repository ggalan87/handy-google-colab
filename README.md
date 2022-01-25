# handy-google-colab
This repository provides a set of scripts and notebooks which enable access of google colab from a local machine using SSH. An additional, although straightforward step is to configure an IDE to use a remote python interpreter. The guide was presented in a [forum post](https://discuss.pytorch.org/t/using-pycharm-to-debug-pytorch-model-on-gce-aws-or-azure/46212/4) and in accompanying [repository](https://github.com/wojtekcz/ml_seminars/tree/master/demo_colab_ssh_access) that contains a tutorial notebook on how to do the stuff (in polish). Here I did a restructure and simplification of the code using a set of scripts.

A relevant repository is [colab-ssh](https://github.com/WassimBenzarti/colab-ssh) which is based on the same principle to connect to the colab, however it utilizes cloudflared for this stuff. Apart from using a public service there are also a self-hosted solutions which I will investigate and integrate later:
- [A curated list about tunneling options](https://github.com/anderspitman/awesome-tunneling)
- [SSH to google colab using frp](https://github.com/toshichi/google_colab_ssh) 


## Prerequisites
The following steps should work for Linux, Windows, macOS. For Windows you need also to have OpenSSH installed as shown in a [relevant guide](https://phoenixnap.com/kb/generate-ssh-key-windows-10).

## Installation steps

### Port forwarding
First we need to create and configure an account in a port forwarding service like [portmap.io](https://portmap.io/). This offers one port mapping for free. This step in required only once.

1. Create & login to an account in [portmap.io](https://portmap.io)
2. Create a [new configuration](https://portmap.io/configs)
   - The configuration name is fixed as 'first'
   - Download the private key. It's name is in the form <username>.first.pem
3. Create a [new mapping](https://portmap.io/mappings)
   - Leave everything as is and fill a port number to the field "Port on your PC". For simplicity I choose the same port as the above.
   - Save the mapping and keep somewhere the rule, which should be in the form:\
      `tcp://<username>-<remote_port>.portmap.host:<remote_port> => <local_port>`
4. Generate a corresponding public key for the downloaded private key with the following command:\
    `ssh-keygen -y -f <username>.first.pem > public_key.pub`

  
### Configuration
Second we need to keep somewhere the configuration files and the keys. I choose to keep them in google drive rather than as plain text in the notebook. Then the colab notebook will mount and use the files from the google drive.
  
1. Create a desired folder structure in google drive. For example:\
    `<google_drive_root>/colab_data/tunnel_options`
2. Upload the private and public keys in this folder
3. Upload a mapping_config.json file containing the port mapping information. A template can be found in this repo.
   
