-- Migrates CashTransactions/AssetTransactions money and quantity columns
-- from FLOAT to DECIMAL(18,8) to remove binary floating-point rounding
-- error from balance/holdings calculations. Run once against an existing
-- database created from an older schema.sql.
USE portfolio_manager;

ALTER TABLE CashTransactions
    MODIFY amount DECIMAL(18,8) NOT NULL;

ALTER TABLE AssetTransactions
    MODIFY qty DECIMAL(18,8) NOT NULL,
    MODIFY price DECIMAL(18,8) NOT NULL,
    MODIFY val DECIMAL(18,8) NOT NULL;
