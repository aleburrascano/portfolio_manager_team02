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
    assetType ENUM('stock', 'crypto', 'bond') NOT NULL,
    ticker VARCHAR(12) NOT NULL,
    qty DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    val DECIMAL(18,8) NOT NULL,
    assetTransactionType ENUM('buy', 'sell') NOT NULL,
    assetTransactionDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    userId INTEGER NOT NULL,
    FOREIGN KEY (userId) REFERENCES Users(userId) ON DELETE CASCADE
);

-- Synthetic bond catalog. 
CREATE TABLE Bonds (
    ticker VARCHAR(12) PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    faceValue DECIMAL(18,8) NOT NULL,
    couponRate DECIMAL(6,4) NOT NULL,
    marketYield DECIMAL(6,4) NOT NULL,
    couponFrequency ENUM('annual', 'semiannual') NOT NULL DEFAULT 'semiannual',
    issueDate DATE NOT NULL,
    maturityDate DATE NOT NULL
);

-- Bond catalog data.
INSERT INTO Bonds (ticker, name, faceValue, couponRate, marketYield, couponFrequency, issueDate, maturityDate) VALUES
    -- US Treasuries
    ('UST2Y',    'US Treasury Note 2Y',              1000, 0.0422, 0.0422, 'semiannual', '2026-07-15', '2028-07-15'),
    ('UST5Y',    'US Treasury Note 5Y',              1000, 0.0437, 0.0437, 'semiannual', '2026-07-15', '2031-07-15'),
    ('UST10Y',   'US Treasury Note 10Y',              1000, 0.0467, 0.0467, 'semiannual', '2026-07-15', '2036-07-15'),
    ('UST20Y',   'US Treasury Bond 20Y',              1000, 0.0521, 0.0521, 'semiannual', '2026-07-15', '2046-07-15'),

    -- Corporates
    ('AAPL2045', 'Apple Inc 3.450% 2045',             1000, 0.0345, 0.0566, 'semiannual', '2015-02-09', '2045-02-09'),
    ('MSFT2030', 'Microsoft Corp 1.350% 2030',        1000, 0.0135, 0.0421, 'semiannual', '2020-09-15', '2030-09-15'),
    ('JNJ2033',  'Johnson & Johnson 4.375% 2033',     1000, 0.0438, 0.0454, 'semiannual', '2023-12-05', '2033-12-05'),
    ('WMT2028',  'Walmart Inc 3.700% 2028',           1000, 0.0370, 0.0396, 'semiannual', '2018-06-26', '2028-06-26'),

    -- Municipals
    ('NYCGO27',  'NYC GO Bonds Fiscal 2017 Ser A',    1000, 0.0500, 0.0487, 'semiannual', '2016-08-01', '2027-08-01'),
    ('CAGO28',   'California GO Refunding Bond',      1000, 0.0300, 0.0290, 'semiannual', '2018-11-01', '2028-11-01'),
    ('CAGO34',   'California GO Bond 7.5% 2034',      1000, 0.0750, 0.0370, 'semiannual', '2004-04-01', '2034-04-01');
