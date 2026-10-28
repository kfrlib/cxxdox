import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
try:
    with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = 'A CxxDox MkDocs plugin for generating C++ documentation from source using libclang.'

setup(
    name='mkdocs-cxxdox',
    version='0.2.2',
    description='MkDocs plugin that generates C++ API documentation from source using libclang.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kfrlib/cxxdox',
    license='Apache-2.0 WITH LLVM-exception',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Plugins',
        'Framework :: MkDocs',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: C++',
        'Topic :: Documentation',
        'Topic :: Software Development :: Documentation',
    ],
    python_requires='>=3.9',
    packages=find_packages(),
    # Bundled libclang binaries and resource headers are extracted from the
    # official LLVM release archive during the CI wheel build
    # (see .github/workflows/build.yml).
    #
    # The recursive '**' glob requires setuptools >= 62.3.0; that version is
    # pinned in pyproject.toml [build-system].requires.
    include_package_data=True,
    package_data={
        'cxxdox_plugin': [
            # libclang shared library (platform-specific binary)
            'libclang21/libclang.dll',
            'libclang21/libclang.so',
            'libclang21/libclang.dylib',
            'libclang21/libclang.so.*',
            'libclang21/libclang.*.dll',
            'libclang21/cindex.py',
            # Clang builtin / resource headers (stddef.h, stdarg.h,
            # immintrin.h, arm_neon.h, …).  These live under:
            #   libclang21/clang/<major>/include/   (explicit -resource-dir)
            #   lib/clang/<major>/include/           (implicit discovery)
            # Both trees are identical copies; the ** glob picks up all
            # nested sub-directories (openmp_wrappers/, sanitizer/, etc.).
            'libclang21/clang/**',
            'lib/clang/**',
            # CSS / JS assets for generated documentation pages
            'assets/*',
        ],
        'cxxdox_plugin.libclang21': [
            'libclang.dll',
            'libclang.so',
            'libclang.dylib',
            'libclang.so.*',
            'libclang.*.dll',
            'cindex.py',
            'clang/**',
        ],
    },
    entry_points={
        'mkdocs.plugins': [
            'cxxdox = cxxdox_plugin.plugin:CxxDoxPlugin',
        ],
        'console_scripts': [
            'cxxdox-search = cxxdox_plugin.search_symbol:main',
            'cxxdox-snippets = cxxdox_plugin.snippets:main',
        ],
    },
    install_requires=[
        'mkdocs>=1.5',
        'mkdocs-material>=9.1.15',
        'parsimonious',
    ],
    extras_require={},
)
