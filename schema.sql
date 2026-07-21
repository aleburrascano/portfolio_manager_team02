CREATE DATABASE portfolio_manager;
USE portfolio_manager;

CREATE TABLE Users (
    userId INTEGER AUTO_INCREMENT PRIMARY KEY,
    walletBalance FLOAT NOT NULL DEFAULT 0
);

CREATE TABLE CashTransactions (
    cashTransactionId INTEGER AUTO_INCREMENT PRIMARY KEY,
    transactionType ENUM('deposit', 'withdraw') NOT NULL,
    amount FLOAT NOT NULL,
    cashTransactionDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    userId INTEGER NOT NULL,
    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE
);

CREATE TABLE StockTransactions (
    stockTransactionId INTEGER AUTO_INCREMENT PRIMARY KEY,
    ticker VARCHAR(5) NOT NULL,
    amount FLOAT NOT NULL,
    price FLOAT NOT NULL,
    stockTransactionType ENUM('buy', 'sell') NOT NULL,
    stockTransactionDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    userId INTEGER NOT NULL,
    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE
);
