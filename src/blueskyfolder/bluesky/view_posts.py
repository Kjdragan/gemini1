import sqlite3
import pandas as pd
from .config import DB_PATH

def view_posts():
    """
    Reads all posts from the database and displays the first 300 records in a pandas DataFrame.
    """
    con = sqlite3.connect(DB_PATH)
    query = "SELECT id, uri, text, author, handle, lang, created_at, reply_to, root_uri, rev, operation, cid FROM posts"
    df = pd.read_sql_query(query, con)
    con.close()

    df['created_at'] = pd.to_datetime(df['created_at'], format='mixed', utc=True)

    print("DataFrame Info:")
    df.info()
    print("\n" + "="*50 + "\n")

    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.colheader_justify', 'left')


    print(df.head(300))

if __name__ == "__main__":
    view_posts()
