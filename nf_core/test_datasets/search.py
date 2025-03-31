import questionary
import rich

from nf_core.test_datasets.test_datasets_utils import (
    MODULES_BRANCH_NAME,
    create_download_url,
    create_pretty_nf_path,
    get_or_prompt_branch,
    list_files_by_branch,
)
from nf_core.utils import nfcore_question_style, rich_force_colors

stdout = rich.console.Console(force_terminal=rich_force_colors())


def search_datasets(maybe_branch, generate_nf_path, generate_dl_url, ignored_file_prefixes):
    branch, all_branches = get_or_prompt_branch(maybe_branch)

    stdout.print("Searching files on branch: ", branch)
    tree = list_files_by_branch(branch, all_branches, ignored_file_prefixes)
    files = sum(tree.values(), [])  # flat representation of tree

    file_selected = False
    while not file_selected:
        selection = questionary.autocomplete(
            "File:",
            choices=files,
            style=nfcore_question_style,
        ).unsafe_ask()

        file_selected = any([selection == file for file in files])
        if not file_selected:
            stdout.print("Please select a file.")

    if generate_nf_path:
        stdout.print(create_pretty_nf_path(selection, branch == MODULES_BRANCH_NAME))
    elif generate_dl_url:
        stdout.print(create_download_url(branch, selection))
    else:
        stdout.print(selection)
