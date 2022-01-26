import os
import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

lib_path = os.path.dirname(os.path.realpath(__file__))
requirements_path = os.path.join(lib_path, 'requirements.txt')

install_requires = []
if os.path.isfile(requirements_path):
    with open(requirements_path) as f:
        install_requires = f.read().splitlines()

print(lib_path, install_requires)

setuptools.setup(
    name="handy-google-colab",
    version="0.1",
    author="George Galanakis",
    author_email="ggalan87@gmail.com",
    description="Access to Google Colab using SSH tunnel",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ggalan87/handy-google-colab",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: The Unlicense (Unlicense)",
        "Operating System :: OS Independent",
    ],
    license_files=('LICENSE.txt',),
    python_requires='>=3.6',
    packages=setuptools.find_packages(),
    include_package_data=True,
    package_data={
        "handy_colab": ["config/*"],
    },
    install_requires=install_requires,
)
