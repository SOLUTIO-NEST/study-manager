from study_manager.judges import get_problem


def main():
    urls = [
        "https://www.acmicpc.net/problem/1003",
        "https://codeforces.com/problemset/problem/4/A",
    ]

    for url in urls:
        problem = get_problem(url)

        print(problem)


if __name__ == "__main__":
    main()