import yfinance as yf
data = yf.download("^GSPC", period="1y")
print(data.tail())