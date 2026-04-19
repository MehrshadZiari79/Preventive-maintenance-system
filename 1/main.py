import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
from database.seed import seed_admin
from views.login_view import LoginView


def main():
    init_db()
    seed_admin()
    app = LoginView()
    app.mainloop()


if __name__ == "__main__":
    main()
