# BuyMe - CS 527 Auction System

## Setup

### 1. Database

The app defaults to the included local SQLite database for quick testing:

```bash
python app.py
```

To run against MySQL for the project requirement, create the database and set `BUYME_DATABASE_URI` before starting Flask:

```bash
mysql -u root -p < setup.sql
set BUYME_DATABASE_URI=mysql+pymysql://buyme_user:password@localhost/buyme
python app.py
```

PowerShell users can set the variable with:

```powershell
$env:BUYME_DATABASE_URI = "mysql+pymysql://buyme_user:password@localhost/buyme"
python app.py
```

### 2. Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python app.py
```

Visit http://localhost:5000.

## Default Accounts

- Admin: `admin` / `admin123`
- Customer rep: `support_rep` / `rep123`
- Sample sellers: `techseller`, `gadgetguru`, `vintagefinds`, `sportsgear` / `pass123`

## Implemented Requirement Coverage

- End-users can register, log in, log out, deactivate accounts, list items, bid, use automatic bidding, save alerts, ask support questions, and anonymize bid history names.
- Search supports keyword, the Electronics category hierarchy, price range, sorting, and category-specific attribute filters.
- Buyers can view bid history for an auction, their own bid history, public buyer/seller auction participation histories, and similar recent items.
- Customer reps can answer end-user questions, edit user info, reset passwords, remove bids, and remove illegal auctions.
- Admins can create customer reps and view total earnings, earnings per item, category, and end-user, plus best-selling items and users.

## Team Category

This BuyMe instance is restricted to Electronics. Item types and required fields are data-driven through the `categories.attributes` column.
The seed data includes multiple distinct listings in every leaf subcategory.

- Electronics
  - Computers
    - Laptops: brand, processor, ram_gb, storage_gb, screen_size_inch, condition
    - Desktops: brand, processor, ram_gb, storage_gb, gpu, condition
  - Phones
    - Smartphones: brand, model, storage_gb, color, carrier, condition
  - Cameras
    - Mirrorless Cameras: brand, model, megapixels, lens_mount, condition
    - DSLR Cameras: brand, model, megapixels, lens_mount, condition

## User Roles

- `buyer_seller`: default, can list items and place bids
- `customer_rep`: can edit users, remove bids, and remove listings
- `admin`: can create reps and view sales reports
