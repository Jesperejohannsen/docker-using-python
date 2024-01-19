import os
import shutil
import ctypes
import platform
import gzip
import tarfile
from io import BytesIO
import urllib.request
import json

CLONE_NEWPID = 0x20000000
CLONE_NEWPID = 0x20000000
def docker_auth(image):
    response = urllib.request.urlopen(
        urllib.request.Request(
            f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/{image}:pull"
        )
    )
    auth_dict = json.loads(response.read().decode())

    return auth_dict["access_token"]
def get_platform():
    os = platform.system().lower()
    architecture = platform.machine()
    if architecture == "x86_64":
        architecture = "amd64"

    return os, architecture
def get_manifest(image, tag, auth_token):
    # It seems like the directions are outdated, it only wants to serve me an OCI image. Let's
    # try to accommodate this.
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.docker.distribution.manifest.v2+json",
    }
    response = urllib.request.urlopen(
        urllib.request.Request(
            f"https://registry.hub.docker.com/v2/library/{image}/manifests/{tag}",
            headers=headers,
        )
    )
    manifest_dict = json.loads(response.read().decode())

    return manifest_dict
def pull_layer(manifest_dict, image, auth_token, output_dir):
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json",
    }
    os, architecture = get_platform()
    for manifest in manifest_dict["manifests"]:
        if (
            "platform" in manifest
            and "architecture" in manifest["platform"]
            and "os" in manifest["platform"]
        ):
            if (
                manifest["platform"]["architecture"] == architecture
                and manifest["platform"]["os"] == os
            ):
                manifest_target = manifest
                break
    image_digest = manifest_target["digest"]
    response = urllib.request.urlopen(
        urllib.request.Request(
            f"https://registry.hub.docker.com/v2/library/{image}/manifests/{image_digest}",
            headers=headers,
        )
    )
    image_manifest = json.loads(response.read().decode())
    layers = image_manifest["layers"]
    digest = layers[0]["digest"]
    response = urllib.request.urlopen(
        urllib.request.Request(
            f"https://registry.hub.docker.com/v2/library/{image}/blobs/{digest}",
            headers=headers,
        )
    )
    layer = response.read()
    tar_gz_data = BytesIO(layer)
    with gzip.open(tar_gz_data, "rb") as z:
        tar_data = BytesIO(z.read())
    with tarfile.open(fileobj=tar_data, mode="r") as t:

        t.extractall(path=output_dir)
def split_tag(image_tag):
    if image_tag.find(":") > -1:
        image, tag = image_tag.split(":")
    else:
        image = image_tag
        tag = "latest"

    return image, tag
def docker_pull(image_tag, target_dir):
    # Separate out the image:
    image, tag = split_tag(image_tag)
    # Auth with Docker.
    auth_token = docker_auth(image)
    # Get the manifest.
    manifest = get_manifest(image, tag, auth_token)
    # Download the layer.

    layer = pull_layer(manifest, image, auth_token, target_dir)
def main():
    command_localpath = sys.argv[3]
    image = sys.argv[2]
    command = sys.argv[3]
    args = sys.argv[4:]
    # Create a temporary directory.
    # Create a temporary directory.
    tempdir = tempfile.TemporaryDirectory()
    # Copy in the command
    shutil.copy(command_localpath, tempdir.name)
    command = "/" + os.path.basename(command_localpath)
    # Pull the docker image and extract it into the tempdir

    docker_pull(image, tempdir.name)
    # Copy in the command, left over from previous stages.
    # shutil.copy(command_localpath, tempdir.name)
    # command = '/' + os.path.basename(command_localpath)
    # Chroot into it.
    # Pretty frustrating: Locally, there are permissions that prevent this. Works remotely though.
    os.chroot(tempdir.name)
    # Enter a new namespace. This virtual env uses Python 3.11, so there's no unshare().
    # The code examples all use something called ctypes. I'll try to look into this.
    libc = ctypes.cdll.LoadLibrary("libc.so.6")
    libc.unshare(CLONE_NEWPID)
    # Run the process; we need to use a try to capture non-zero error codes.
    try:
        # capture_output=True is equivalent to Popen with stdout and stderr =subprocess.PIPE
        completed_process = subprocess.run(
            [command, *args], capture_output=True, check=True
        )
        # We want to print these exactly, without an additional newline.
        print(completed_process.stdout.decode("utf-8"), end="")
        print(completed_process.stderr.decode("utf-8"), end="", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode("utf-8"), end="")
        print(e.stderr.decode("utf-8"), end="", file=sys.stderr)
        sys.exit(e.returncode)
if __name__ == "__main__":
    main()