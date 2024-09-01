import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # query database to get users stocks and shares
    users_stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])

    # get user's balance(cash)
    cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"])[0]["cash"]
    # initiate variables for total values
    total_values = round(float(cash), 2)
    grand_total = round(float(cash), 2)
    # iterate over all stock and add price and total values
    for users_stock in users_stocks:
        quote = lookup(users_stock["symbol"])
        users_stock["name"] = quote["symbol"]
        users_stock["symbol"] = quote["symbol"]
        users_stock["price"] = round(float(quote["price"]), 2)
        users_stock["value"] = round(float(users_stock["price"]) * int(users_stock["total_shares"]), 2)
        users_stock["total_shares"] = users_stock["total_shares"]
        total_values = round(float(total_values) + int(users_stock["value"]), 2)
        grand_total = round(float(grand_total) + int(users_stock["value"]), 2)
        cash = f"{float(cash):.2f}"
        total_values = f"{total_values:.2f}"
        grand_total = f"{grand_total:.2f}"
    return render_template("index.html", users_stocks=users_stocks, cash=cash, total_values=total_values, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # if user reach here via submitting form(post)
    if request.method == "POST":
        # get symbol from form
        symbl = request.form.get("symbol").upper()
        # get shares from form
        shrs = request.form.get("shares")

        # validate/ensure symbol is provided
        if not symbl:
            return apology("must provide symbol")
        # validate correct from of shares is provided
        elif not shrs or not shrs.isnumeric() or int(shrs) <= 0:
            return apology("must provide a positive integer number of shares")
        # lookup symbol
        stock_quote = lookup(symbl)
        if stock_quote is None:
            return apology("symbol not found")

        # set price and total cost from the lookup
        price = round(float(stock_quote["price"]), 2)
        total_cost = round(float(shrs) * price, 2)

        # query database and check if user balance is enough
        cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"] )[0]["cash"]
        if cash < total_cost:
            return apology("Cash balance not enough")
        else:

            # add to history table
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES (:user_id, :symbl, :shrs, :price)", user_id=session["user_id"], symbl=symbl, shrs=shrs, price=price)

            cash = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id=session["user_id"] )[0]["cash"]
            cash = round(float(cash - total_cost), 2)
            # update user table
            db.execute("UPDATE users SET cash = ? WHERE id = ?",
            cash, session["user_id"])


            flash(f"Bought {shrs} shares of {symbl} for ${price:.2f}! You have ${cash:.2f} in your account.")



            return redirect("/")
    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # Query database for username & transactions
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamo DESC", session["user_id"])

    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure that a username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure a password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username to know if already exists
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # Ensure symbol is not blank
        if symbol == "":
            return apology("input is blank", 400)

        stock_quote = lookup(symbol)

        if not stock_quote:
            return apology("INVALID SYMBOL", 400)
        return render_template("quote.html", quote=stock_quote)

    # User reached route via GET
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    #forget any user session
    session.clear()

    # reached route via Post(i.e subitting a form via POST)
    if request.method == "POST":
        # validate that a username was submitted
        if not request.form.get("username"):
            return apology("You must provide a Username", 400)

        # validate that a password was submitted
        elif not request.form.get("password"):
            return apology("You must enter a password", 400)

        # validate that a password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("Confirm your password", 400)
        # ensure password and confirm password match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("Your Password does not match", 400)
        # query database to ensure the username does not exists in database
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username") )
        if len(rows) == 1:
            return apology("This Username already exists", 400)
        # insert new username to database
        rows = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")) )
        # query data for the new user
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username") )

        # remeber which user has logged in
        session["user_id"] = rows[0]["id"]
        # Redirect to home page
        return redirect("/")

    # reached route via GET (i.e. as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions where :user_id = :user_id GROUP BY symbol HAVING total_shares > 0", user_id=session["user_id"])
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")

        # Ensure symbol is not blank
        if not symbol:
            return apology("MISSING SYMBOL", 400)
        elif not shares or not shares.isnumeric() or int(shares) <= 0:
            return apology("provide a positive share number", 400)
        else:
            shares = int(shares)


        for stock in stocks:
            if stock["symbol"] == symbol:
                if stock["total_shares"] < shares:
                    return apology("Not enough shares")
                else:
                    # get quote
                    stock_quote = lookup(symbol)
                    if stock_quote is None:
                        return apology("INVALID SYMBOL", 400)
                    price = stock_quote["price"]
                    total_sale = shares * price

                    # update table
                    db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", total_sale, session["user_id"])
                    # add to history table
                    db.execute("INSERT INTO transactions (user_id, symbol, shares, price) VALUES(?, ?, ?, ?)", session["user_id"], stock_quote['symbol'], int(-shares), stock_quote['price'])
                    flash(f"Sold {shares} shares of {symbol} for {usd(total_sale)}")
                    return redirect("/")
        return apology("symbol not found")

    # User reached route via GET
    else:
        return render_template("sell.html", stocks=stocks)
