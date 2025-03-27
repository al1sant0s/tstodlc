from colorama import Style


def report_progress(prefix_str, parsing_info):
    # Clear line.
    print(150 * " ", end="\r")
    # Print progress.
    print(f"{prefix_str} {parsing_info}", end="\r")


def colorprint(style, message, end="\n"):
    print(style + message, end=end)
    print(Style.RESET_ALL)
