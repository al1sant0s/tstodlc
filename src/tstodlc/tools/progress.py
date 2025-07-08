from colorama import Style, Fore

def progress_str(n, total, message):
    return (
        message
        + Style.BRIGHT
        + Fore.CYAN
        + f"- Progress ({n * 100 / total:.2f}%)"
        + Style.RESET_ALL
    )


def report_progress(prefix_str, parsing_info):
    # Clear line.
    print(150 * " ", end="\r")
    # Print progress.
    print(f"{prefix_str} {parsing_info}", end="\r")


def colorprint(style, message, end="\n"):
    print(style + message, end=end)
    print(Style.RESET_ALL)
