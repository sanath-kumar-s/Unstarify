import sys
from PySide6.QtWidgets import QApplication
from gui import GitHubStarsApp

def main() -> None:
    try:
        app = QApplication(sys.argv)
        window = GitHubStarsApp()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting application: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
