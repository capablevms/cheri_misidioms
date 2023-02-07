mkdir artifact
cd artifact
mkdir sysroot
export MMUSL_SYSROOT=`pwd`/sysroot
mkdir clang
export MMUSL_CLANG=`pwd`/clang
mkdir compiler-rt
export MMUSL_COMPILER_RT=`pwd`/compiler-rt
mkdir toolchain
export MMUSL_MORELLO=`pwd`/toolchain
cd ..
export MMUSL_LLVM_SOURCES=/home/memalloc/cheri_misidioms/data/cheri_alloc_last/cheribuild/morello-llvm-project/
export MMUSL_SOURCE=/home/memalloc/musl-libc/
export MMUSL_LLVM=/home/memalloc/cheri_misidioms/data/cheri_alloc_last/cheribuild/output/morello-sdk/

CC=${MMUSL_LLVM}/bin/clang ./tools/build-morello.sh musl-headers ${MMUSL_SOURCE} ${MMUSL_SYSROOT} aarch64-unknown-linux-musl_purecap
CC=${MMUSL_LLVM}/bin/clang ./tools/build-morello.sh crt ${MMUSL_LLVM_SOURCES} ${MMUSL_SYSROOT} aarch64-unknown-linux-musl_purecap
CC=${MMUSL_LLVM}/bin/clang ./tools/build-morello.sh compiler-rt ${MMUSL_LLVM_SOURCES} ${MMUSL_LLVM} ${MMUSL_COMPILER_RT} ${MMUSL_SYSROOT} aarch64-unknown-linux-musl_purecap
CC="${MMUSL_LLVM}/bin/clang --rtlib=compiler-rt" ./configure --enable-morello --prefix=${MMUSL_SYSROOT} --target=aarch64-unknown-linux-musl_purecap

make -j5
make install


## Compile ${MMUSL_LLVM}/bin/clang --rtlib=compiler-rt -march=morello+c64 --target=aarch64-linux-musl_purecap --sysroot ${MMUSL_SOURCE}/artifacts/musl validate.c -o validate_linux -static
