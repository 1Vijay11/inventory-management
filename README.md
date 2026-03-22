# Inventory Management System

A full-stack inventory management system built with Django that allows users to manage products, track stock levels in real time, and organize inventory using categories and subcategories.

This project was developed independently to demonstrate backend data modeling, frontend interactivity, and full-stack integration in a practical, real-world scenario.

---

## 🌐 Live Demo

🔗 **Live Application:** [Add your Render link here]

### Demo Account (for employers/reviewers)
> A demo account is provided for evaluation purposes:

- **Username:** [add here]
- **Password:** [add here]

---

## 🚀 Features

### 📦 Inventory Management
- Create, edit, and manage products
- Track stock quantities and pricing
- Mark items as discontinued

### ⚡ Real-Time Stock Updates
- Increment/decrement stock without page refresh
- Uses JavaScript (Fetch API) with Django backend
- UI updates instantly after server response

### 🔍 Advanced Filtering & Search
- Search products by name
- Filter by **multiple categories**
- Toggle:
  - Out-of-stock items
  - Discontinued items
- Filters persist across sorting

### ↕️ Sorting System
- Sort by:
  - Name
  - SKU
  - Price
  - Stock quantity
- Supports ascending and descending order
- Maintains filters during sorting

### 🗂️ Subcategory Grouping
- Products grouped under subcategories
- Collapsible rows for better organization
- Aggregated values displayed per subcategory

### 📊 Derived Data
- Total inventory value
- Total stock count
- Per-product total value (price × stock)
- Subcategory-level aggregations

### 🎨 Custom UI/UX
- Fully custom styling using CSS variables
- Responsive layout (mobile-friendly table behavior)
- Visual indicators:
  - Discontinued items
  - Category tags
- Auto-dismissing alerts with user interaction override

---

## 🛠️ Tech Stack

### Backend
- Python
- Django
- Django ORM
- PostgreSQL (via Neon)

### Frontend
- HTML (Django Templates)
- CSS (custom design system)
- JavaScript (Fetch API / AJAX)
- Bootstrap (customized)

### Deployment
- Render (web hosting)
- Neon (serverless PostgreSQL database)

---

## 🗄️ Database Design

The application uses a relational database with three main models:

### Tables
- **Product**
- **Category**
- **SubCategory**

### Relationships
- A **Product** can belong to multiple **Categories** (Many-to-Many)
- A **Product** belongs to one **SubCategory** (Foreign Key)
- A **SubCategory** contains multiple **Products**

### Data Integrity
- Database-level constraints ensure:
  - Price ≥ 0
  - Stock ≥ 0
  - SKU ≥ 0

### Derived Properties
- Product total value (`price × stock`)
- Subcategory:
  - Total stock
  - Total value
  - Min/max price range

---

## 🧩 Entity Relationship Diagram

![ERD Placeholder](./docs/erd-placeholder.png)

---

## ⚙️ How It Works

### Filtering & Sorting
- Uses query parameters (`GET`) to handle filtering and sorting
- State is preserved across interactions (e.g., filtering + sorting together)

### Combined Data Rendering
- Products and subcategories are merged into a single dataset
- Allows grouped display with collapsible UI behavior

### Real-Time Updates
- Stock buttons trigger asynchronous requests to the backend
- Django processes the update and returns JSON
- Frontend updates:
  - Stock values
  - Subcategory totals
  - Dashboard summary cards

---

## 🎯 UI / UX Design Decisions

- Collapsible subcategories reduce visual clutter
- Inline stock controls improve efficiency
- Mobile responsiveness handled by selectively hiding columns
- Consistent design system using reusable CSS variables
- Feedback system (alerts) designed to be non-intrusive but interactive

---

## 📸 Screenshots

### Dashboard
![Dashboard Placeholder](./docs/dashboard.png)

### Filtering & Search
![Filter Placeholder](./docs/filter.png)

### Subcategory View
![Subcategory Placeholder](./docs/subcategory.png)

### Add/Edit Product
![Form Placeholder](./docs/form.png)

---

## ⚠️ Notes

- This project was built independently as a learning and portfolio project
- Code comments are written primarily for personal clarity and understanding
- Some implementation decisions prioritize readability and learning over production-level optimization

---

## 🔮 Future Improvements

- Implement a **safe delete system**
- Enhance sorting capabilities across more fields
- Improve search with partial matching and advanced filters
- Expand category system for more flexible organization
- Add authentication system with role-based access

---

## 🧪 Local Setup

```bash
# Clone the repository
git clone https://github.com/your-username/inventory-system.git

# Navigate into the project
cd inventory-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver