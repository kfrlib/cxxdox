import os
import argparse
import glob
import codecs
import re
import subprocess
import tempfile
import sys

exec_suffix = '.exe' if sys.platform.startswith('win32') else ''


def execute_example(name, code, template_path, output_path, include_dirs):
    print(name, '...')

    builddir = tempfile.mkdtemp()
    print(builddir)

    cppfile = os.path.join(builddir, 'main.hpp')

    open(cppfile, 'w').write(code)

    if subprocess.call(['cmake', '-DCMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE=' + builddir + '', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_FLAGS=-I\"' + include_dirs + '\" -DSNIPPET=\\"' + cppfile + '\\"', template_path], cwd=builddir) == 0:

        if subprocess.call(['cmake', '--build', '.', '--config', 'Release'], cwd=builddir) == 0:
            subprocess.call(['ls', '-la'], cwd=builddir)
            subprocess.call(['./main'], cwd=builddir)
            output = subprocess.check_output([os.path.join(builddir, 'main')+exec_suffix], cwd=builddir)

            print('ok, writing output...')

            open(os.path.join(output_path, name) + '.md',
                 'w').write('```\n' + output.decode('utf-8').strip() + '\n```')

    else:
        print('Can`t configure example: {}'.format(name))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Run markdown code examples and save output & images')
    parser.add_argument('input_path', help='path to markdown files')
    parser.add_argument('template_path', help='path C++ project template')
    parser.add_argument('include_dirs', help='include directories')

    args = parser.parse_args()

    print('Running examples in ', args.input_path + os.path.sep + '*.md', '...')

    filenames = glob.glob(
        args.input_path + os.path.sep + '*.md', recursive=True)

    for filename in filenames:
        print(filename, '...')
        md = codecs.open(filename, 'r', encoding='utf-8').read()
        for r in re.finditer(r'```c\+\+ tab="([a-zA-Z0-9_-]).cpp"\s+(.*?)\s+```', md, re.DOTALL | re.MULTILINE):
            execute_example(r.group(1), r.group(2), args.template_path, os.path.join(
                args.input_path, 'fragments'), args.include_dirs)
