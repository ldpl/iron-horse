print("[RENDER LANG] render_lang.py")

import iron_horse
import utils
from polar_fox import git_info

import shutil
import os

currentdir = os.curdir
from time import time

import sys

sys.path.append(os.path.join("src"))  # add to the module search path

import codecs  # used for writing files - more unicode friendly than standard open() module

# chameleon used in most template cases
from chameleon import PageTemplateLoader

# setup the places we look for templates
templates = PageTemplateLoader(os.path.join(currentdir, "src", "templates"))

# get args passed by makefile
makefile_args = utils.get_makefile_args(sys)

lang_src = os.path.join(currentdir, "src", "lang")
lang_dst = os.path.join(iron_horse.generated_files_path, "lang")

if os.path.exists(lang_dst):
    shutil.rmtree(lang_dst)
shutil.copytree(lang_src, lang_dst)
hint_file = codecs.open(
    os.path.join(lang_dst, "_lang_files_here_are_generated.txt"), "w", "utf8"
)
hint_file.write(
    "Don't edit the lang files here.  They're generated by the build script. \n Edit the ones in lang_src instead."
)
hint_file.close()


def main():
    start = time()
    iron_horse.main()
    consists = iron_horse.ActiveRosters().consists_in_buy_menu_order

    languages_with_generation = ("english",)
    for i in languages_with_generation:
        # compile strings to single lang file - english
        lang_template = templates[i + ".pylng"]

        src_file = codecs.open(os.path.join(lang_src, i + ".lng"), "r", "utf8")
        dst_file = codecs.open(os.path.join(lang_dst, i + ".lng"), "w", "utf8")
        lang_content = src_file.read()
        lang_content = lang_content + lang_template(
            consists=consists,
            makefile_args=makefile_args,
            git_info=git_info,
            utils=utils,
        )
        dst_file.write(lang_content)
        dst_file.close()

    print(format((time() - start), ".2f") + "s")


if __name__ == "__main__":
    main()
