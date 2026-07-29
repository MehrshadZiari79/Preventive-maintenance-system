import sys
import os

# Add project root to path (only needed if you run from outside)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from views.login_view import LoginView


def main():
    # Do NOT initialize database here – let login screen appear first
    app = LoginView()
    app.mainloop()


if __name__ == "__main__":
    main()