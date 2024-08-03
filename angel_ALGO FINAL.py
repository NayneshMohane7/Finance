from SmartApi import SmartConnect
import os
import urllib
import json
from pyotp import TOTP
import socket
socket.getaddrinfo('localhost', 8080)
import pyotp
from talib.abstract import *
from talib.abstract import _ta_lib
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from time import time, sleep
import threading
import warnings
warnings.filterwarnings('ignore')
import requests

from pip._internal import main as install

install(["install","ta-lib"])

import credentials1

key_path = r"C:\ProgramData\Anaconda3"
os.chdir(key_path)
token ='R5I2SUBWKPK4GQ6JL5ZQMCJF64'
# "open("key.txt","r").read().split()"
key_secret = ""

obj=SmartConnect(api_key=key_secret[0])
data = obj.generateSession(key_secret[2],key_secret[3],pyotp.TOTP(token).now())

feed_token = obj.getfeedToken()

SYMBOL_LIST = ['ICICIBANK','BHARTIARTL','RELIANCE']
TRADED_SYMBOL = []
timeFrame = 60 + 5 #5 sec coz dealy repsone of historical API

def place_order(token,symbol,qty,buy_sell,ordertype,price,variety= 'NORMAL',exch_seg='NSE',triggerprice=0):
    try:
        orderparams = {
            "variety": variety,
            "tradingsymbol": symbol,
            "symboltoken": token,
            "transactiontype": buy_sell,
            "exchange": exch_seg,
            "ordertype": ordertype,
            "producttype": "INTRADAY",
            "duration": "DAY",
            "price": price,
            "squareoff": "0",
            "stoploss": "0",
            "quantity": qty,
            "triggerprice":triggerprice
            }
        orderId=credentials1.SMART_API_OBJ.placeOrder(orderparams)
        print("The order id is: {}".format(orderId))
    except Exception as e:
        print("Order placement failed: {}".format(e.message))

def intializeSymbolTokenMap():
    url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
    d = requests.get(url).json()
    global token_df
    token_df = pd.DataFrame.from_dict(d)
    token_df['expiry'] = pd.to_datetime(token_df['expiry'])
    token_df = token_df.astype({'strike': float})
    credentials1.TOKEN_MAP = token_df
    print(token_df)

def getTokenInfo (symbol, exch_seg ='NSE',instrumenttype='OPTIDX',strike_price = '',pe_ce = 'CE'):
    df = credentials1.TOKEN_MAP
    strike_price = strike_price*100
    if exch_seg == 'NSE':
        eq_df = df[(df['exch_seg'] == 'NSE') & (df['symbol'].str.contains('EQ')) ]
        return eq_df[eq_df['name'] == symbol]
    elif exch_seg == 'NFO' and ((instrumenttype == 'FUTSTK') or (instrumenttype == 'FUTIDX')):
        return df[(df['exch_seg'] == 'NFO') & (df['instrumenttype'] == instrumenttype) & (df['name'] == symbol)].sort_values(by=['expiry'])
    elif exch_seg == 'NFO' and (instrumenttype == 'OPTSTK' or instrumenttype == 'OPTIDX'):
        return df[(df['exch_seg'] == 'NFO') & (df['instrumenttype'] == instrumenttype) & (df['name'] == symbol) & (df['strike'] == strike_price) & (df['symbol'].str.endswith(pe_ce))].sort_values(by=['expiry'])


def calculate_inidcator(res_json):
    columns = ['timestamp','O','H','L','C','V']
    df = pd.DataFrame(res_json['data'], columns=columns)
    #df['timestamp'] = pd.to_datetime(df['timestamp'],format = '%Y-%m-%dT%H:%M:%S')
    df['EMA'] = _ta_lib.EMA(df.C, timeperiod=20)
    df['RSI'] = _ta_lib.RSI(df.C, timeperiod=14)
    df['ATR'] = _ta_lib.ATR(df.H, df.L, df.C, timeperiod=20)
    df['CROSS_UP'] = df['CROSS_DOWN'] =df['RSI_UP'] = 0
    df = df.round(decimals=2)
    
    for i in range(20,len(df)):
        if df['C'][i-1]<= df['EMA'][i-1] and df['C'][i] > df['EMA'][i]:
            df['CROSS_UP'][i] = 1
        if df['C'][i-1] >= df['EMA'][i-1] and df['C'][i] < df['EMA'][i]:
            df['CROSS_DOWN'][i] = 1
        if df['RSI'][i] > 50 : 
            df['RSI_UP'][i] = 1 
   
    print(df.tail(10))
    return df


def getHistoricalAPI(token,interval= 'ONE_MINUTE'):
    to_date= datetime.now()
    from_date = to_date - timedelta(days=5)
    from_date_format = from_date.strftime("%Y-%m-%d %H:%M")
    to_date_format = to_date.strftime("%Y-%m-%d %H:%M")
    try:
        historicParam={
        "exchange": "NSE",
        "symboltoken": token,
        "interval": interval,
        "fromdate": from_date_format, 
        "todate": to_date_format
        }
        candel_json  = credentials1.SMART_API_OBJ.getCandleData(historicParam)
        return calculate_inidcator(candel_json)
    except Exception as e:
        print("Historic Api failed: {}".format(e.message))

def checkSingnal():
    start = time()
    global TRADED_SYMBOL
    
    for symbol in SYMBOL_LIST :
        if symbol not in TRADED_SYMBOL:
            tokenInfo = getTokenInfo(symbol).iloc[0]
            token = tokenInfo['token']
            symbol = tokenInfo['symbol']
            print(symbol, token)
            candel_df = getHistoricalAPI(token)
            if candel_df is not None :
                latest_candel = candel_df.iloc[-1]
                if latest_candel['CROSS_UP'] == 1 and latest_candel['RSI_UP'] ==1:
                   
                    ltp = latest_candel['C']
                    SL = ltp -  2*latest_candel['ATR']
                    target = ltp + 5*latest_candel['ATR']
                    qty = 6   #qunatity to trade
                    
                    res1= place_order(token,symbol,qty,'BUY','MARKET',0) #buy order
                    res2 = place_order(token,symbol,qty,'SELL','STOPLOSS_MARKET',0,variety='STOPLOSS',triggerprice= SL) #SL order
                    res3 = place_order(token,symbol,qty,'SELL','LIMIT',target) #taget order
                    print(res1, res2 , res3)
                    print(f'Order Placed for {symbol} SL {SL}  TGT {target} QTY {qty} at {datetime.now()}')
                    TRADED_SYMBOL.append(symbol)


    interval = timeFrame - (time()-start)   
    print(interval)
    threading.Timer(interval, checkSingnal).start()



if __name__ == '__main__':
    intializeSymbolTokenMap()
    obj=SmartConnect(api_key=credentials1.API_KEY)
    data = obj.generateSession(key_secret[2],key_secret[3],pyotp.TOTP(token).now())
    credentials1.SMART_API_OBJ = obj
    feed_token = obj.getfeedToken()
   
    interval = timeFrame - datetime.now().second
    print(f"Code run after {interval} sec")
    sleep(interval)
    checkSingnal()

   
