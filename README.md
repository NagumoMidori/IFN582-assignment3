# IFN582 Assignment 3
# HI
## Prerequisites
- Python 3.10 or newer
- MySQL Server installed locally and running
- `pip` available in your environment

## Setup Instructions
1. **Install MySQL**  
   Ensure that a local MySQL Server instance is available. Create a user/password combination that you can use for this project.

2. **Configure the database connection**  
   Open `project/__init__.py` and update the line  
   ```python
   app.config['MYSQL_PASSWORD'] = 'password' #enter your own password of the mysql here!!!
   ```
   so that it matches your local MySQL password. Adjust `MYSQL_USER`, `MYSQL_DB`, and `MYSQL_HOST` if your setup differs from the defaults.

3. **Create the database schema**  
   Run the provided SQL script against your MySQL server. For example:  
   
   ```bash
   mysql -u root -p < database.sql
   ```
   Replace `root` with the MySQL user you intend to use. Enter the password when prompted.
   
   ⚠️⚠️ Or directly run the .sql file in mysql workbench, it may much easier.
   
4. **Install Python dependencies**  
   From the project root, install all requirements:  
   
   ```bash
   pip install -r requirements.txt
   ```

## Run the Application

Start the Flask application with:
```bash
python run.py
```
The development server runs on `http://127.0.0.1:8888/` by default. If you make changes to the source code, Flask reloads automatically while `app.debug` remains enabled.

## Test Accounts

Here are some test accounts you can use to explore the application:

*   **Admin User**
    *   **Username:** `admin1`
    *   **Password:** `123456`

*   **Vendor User**
    *   **Email:** `loremipsum@project582.com`
    *   **Password:** `123456`

*   **Customer User**
    *   **Email:** `dusty@example.com`
    *   **Password:** `123456`
