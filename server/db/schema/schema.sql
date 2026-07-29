CREATE DATABASE portfolio_manager;
USE portfolio_manager;

CREATE TABLE Users (
    userId INTEGER AUTO_INCREMENT PRIMARY KEY,
    firstName VARCHAR(32) NOT NULL,
    lastName VARCHAR(32) NOT NULL
);

CREATE TABLE CashTransactions (
    cashTransactionId INTEGER AUTO_INCREMENT PRIMARY KEY,
    cashTransactionType ENUM('deposit', 'withdraw') NOT NULL,
    amount DECIMAL(18,8) NOT NULL,
    cashTransactionDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    userId INTEGER NOT NULL,
    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE
);

CREATE TABLE AssetTransactions (
    assetTransactionId INTEGER AUTO_INCREMENT PRIMARY KEY,
    assetType ENUM('stock', 'crypto') NOT NULL,
    ticker VARCHAR(12) NOT NULL,
    qty DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    val DECIMAL(18,8) NOT NULL,
    assetTransactionType ENUM('buy', 'sell') NOT NULL,
    assetTransactionDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    userId INTEGER NOT NULL,
    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE
);
