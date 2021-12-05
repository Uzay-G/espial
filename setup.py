from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt', encoding='utf-8') as f:
    all_reqs = f.read().split('\n')
    install_requires = [x.strip() for x in all_reqs]

setup(
    name='motif_mesh',
    version='0.1.0',
    author="Uzay-G",
    author_email="halcyon@disroot.org",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
    ],
    packages=find_packages(),
    install_requires=install_requires,
    entry_points={"console_scripts": ["mesh=mesh:motif_mesh"]}
)
