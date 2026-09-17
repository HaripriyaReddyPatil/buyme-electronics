# BuyMe Electronics

**Full-Stack Electronics Auction Marketplace**

BuyMe Electronics is a Flask-based web application that allows users to list electronics for auction, place bids, manage bidding activity, search product categories, and interact with customer support. The platform also includes separate tools for customer representatives and administrators.

## Overview

The application supports three user roles:

- Buyers and sellers
- Customer representatives
- Administrators

Users can create accounts, list electronics for auction, place manual or automatic bids, search listings, view bidding history, and manage alerts.

Customer representatives can help manage users, bids, listings, and support requests, while administrators can manage representatives and review marketplace activity and sales reports.

## Key Features

### User Accounts

Users can:

- Register and log in
- Log out securely
- Update account information
- Deactivate their account
- View personal activity and bidding history

### Auction Listings

Sellers can:

- Create auction listings
- Select electronics categories and subcategories
- Add category-specific product information
- Set auction details
- Review their listing activity

### Bidding System

Buyers can:

- Place bids on active auctions
- Use automatic bidding
- View auction bid history
- Review their own bidding activity
- View buyer and seller participation history
- Find similar recent items

### Search and Filtering

Listings can be searched and filtered using:

- Keywords
- Electronics category hierarchy
- Price range
- Sorting options
- Category-specific attributes

### Alerts

Users can save alerts for products or auction conditions they are interested in.

### Customer Support

Users can submit questions through the platform.

Customer representatives can:

- Respond to user questions
- Edit user information
- Reset user passwords
- Remove inappropriate bids
- Remove invalid or prohibited auction listings

### Administrative Dashboard

Administrators can:

- Create customer representative accounts
- Review total marketplace earnings
- View earnings by item
- View earnings by category
- View earnings by user
- Identify best-selling items
- Review top marketplace users

## Product Categories

The marketplace focuses on electronics and supports structured category-specific attributes.

### Electronics

#### Computers

**Laptops**

- Brand
- Processor
- RAM
- Storage
- Screen size
- Condition

**Desktops**

- Brand
- Processor
- RAM
- Storage
- GPU
- Condition

#### Phones

**Smartphones**

- Brand
- Model
- Storage
- Color
- Carrier
- Condition

#### Cameras

**Mirrorless Cameras**

- Brand
- Model
- Megapixels
- Lens mount
- Condition

**DSLR Cameras**

- Brand
- Model
- Megapixels
- Lens mount
- Condition

Category-specific fields are data-driven through the database configuration.

## User Roles

### Buyer / Seller

The default user role.

Users can:

- Create auction listings
- Place bids
- Use automatic bidding
- Search and filter products
- View bidding activity
- Manage alerts
- Ask support questions

### Customer Representative

Customer representatives can:

- Respond to support requests
- Edit user information
- Reset passwords
- Remove bids
- Remove invalid listings

### Administrator

Administrators can:

- Create customer representative accounts
- Access sales reports
- Review marketplace earnings
- Analyze best-selling items and users

## Tech Stack

### Backend

- Python
- Flask
- SQLite

### Frontend

- HTML
- CSS
- JavaScript
- Jinja templates

### Database

- SQLite
- SQL initialization scripts

### Development

- Git
- GitHub

## Project Structure

```text
buyme-electronics/
├── app.py
├── requirements.txt
├── setup.sql
│
├── instance/
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
├── templates/
│   ├── admin_dashboard.html
│   ├── base.html
│   ├── index.html
│   ├── item_detail.html
│   ├── login.html
│   ├── new_item.html
│   ├── profile.html
│   ├── questions.html
│   ├── register.html
│   ├── rep_dashboard.html
│   ├── rep_edit_user.html
│   ├── search.html
│   ├── support.html
│   └── user_history.html
│
└── README.md
```

## Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/HaripriyaReddyPatil/buyme-electronics.git
cd buyme-electronics
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

For Windows:

```bash
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start the application

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

## Demo Accounts

The project includes sample accounts for local demonstration.

### Administrator

```text
Username: admin
Password: admin123
```

### Customer Representative

```text
Username: support_rep
Password: rep123
```

### Sample Seller Accounts

```text
techseller
gadgetguru
vintagefinds
sportsgear
```

Sample password:

```text
pass123
```

These credentials are intended only for local demonstration.

## Database

The application uses SQLite for local persistence.

The repository includes `setup.sql` for database initialization and sample data setup.

## Screenshots

Screenshots can be added here to show:

- Home page
- Auction listing
- Search and filtering
- User dashboard
- Customer representative dashboard
- Administrator dashboard

## Team Project

BuyMe Electronics was developed as a collaborative software project. The application combines auction management, bidding workflows, search and filtering, support tools, and administrative reporting in a Flask-based system.

## Future Enhancements

- Production database deployment
- Email notifications for auction activity
- Payment integration
- Improved authentication and session security
- REST API support
- Automated testing
- Docker deployment
- CI/CD with GitHub Actions

