FROM ubuntu:latest

RUN apt update && \
    DEBIAN_FRONTEND=noninteractive apt install -y \
        autoconf \
        automake \
        bison \
        clang \
        cloc \
        cmake \
        flex \
        git \
        libarchive-dev \
        libarchive-tools \
        libattr1-dev \
        libbz2-dev \
        libcap-ng-dev \
        libglib2.0-dev \
        libpixman-1-dev \
        libtool \
        make \
        mercurial \
        ninja-build \
        pkg-config \
        samba \
        software-properties-common \
        texinfo \
        time \
        wget

RUN add-apt-repository -y ppa:deadsnakes/ppa && \
    DEBIAN_FRONTEND=noninteractive apt install -y python3.10

RUN useradd -m -s /bin/bash memalloc
USER memalloc
WORKDIR /home/memalloc
ENV PATH="${PATH}:/home/memalloc/.local/bin"

RUN wget https://bootstrap.pypa.io/get-pip.py && \
    python3.10 get-pip.py

RUN ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_ed25519 < /dev/null

RUN git clone --depth 1 https://github.com/CTSRD-CHERI/cheribuild

RUN git clone --depth 1 https://github.com/capablevms/cheri_misidioms && \
    find /home/memalloc/cheri_misidioms -name build.sh -exec chmod u+x {} \; &&
    pip3.10 install -r /home/memalloc/cheri_misidioms/data/requirements.txt

WORKDIR /home/memalloc/cheri_misidioms/data
