#!/usr/bin/env python3
"""Generate a 10,000-row stress test CSV with 9,000 valid + 1,000 edge cases.

Usage:
    python scripts/generate_stress_csv.py [--output PATH] [--count N]

The generated CSV exercises the full pipeline: valid candidates, missing fields,
invalid phones/emails, duplicates, blank strings, case variations, and extra whitespace.
"""

from __future__ import annotations

import argparse
import csv
import random
import string
import sys
from pathlib import Path

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan",
    "Krishna", "Ishaan", "Priya", "Sneha", "Ananya", "Riya", "Pooja", "Meera",
    "Kavya", "Nidhi", "Aditi", "Sanya", "Rahul", "Karan", "Rohan", "Vikram",
    "Amit", "Suresh", "Neha", "Divya", "Swati", "Anjali", "Arun", "Deepak",
    "Manish", "Raj", "Akash", "Naveen", "Gaurav", "Siddharth", "Pranav", "Harsh",
]

LAST_NAMES = [
    "Sharma", "Verma", "Kumar", "Gupta", "Singh", "Patel", "Mehta", "Jain",
    "Rao", "Nair", "Iyer", "Kapoor", "Malhotra", "Khanna", "Chopra", "Bhatia",
    "Reddy", "Das", "Roy", "Ghosh", "Banerjee", "Sen", "Dutta", "Pillai",
    "Menon", "Shah", "Thakur", "Mishra", "Pandey", "Trivedi", "Joshi", "Saxena",
]

COMPANIES = [
    "Google", "Microsoft", "Amazon", "Meta", "Apple", "Infosys", "TCS", "Wipro",
    "Adobe", "Accenture", "Cognizant", "Paytm", "Flipkart", "Uber", "Netflix",
    "IBM", "Oracle", "SAP", "Salesforce", "VMware", "Intel", "Nvidia", "Samsung",
    "Capgemini", "HCL", "Tech Mahindra", "Zoho", "Freshworks", "Razorpay",
]

TITLES = [
    "Software Engineer", "Data Analyst", "Backend Developer", "Frontend Developer",
    "Full Stack Developer", "ML Engineer", "DevOps Engineer", "Cloud Engineer",
    "Data Engineer", "AI/ML Intern", "SDE Intern", "Product Manager",
    "QA Engineer", "Security Engineer", "Platform Engineer", "Mobile Developer",
]

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "example.com", "hotmail.com"]


def _random_phone() -> str:
    """Generate a random valid Indian mobile number (10 digits starting with 6-9)."""
    first = random.choice("6789")
    rest = "".join(random.choices(string.digits, k=9))
    return first + rest


def _random_email(first: str, last: str) -> str:
    domain = random.choice(DOMAINS)
    separator = random.choice([".", "_", ""])
    suffix = random.choice(["", str(random.randint(1, 999))])
    return f"{first.lower()}{separator}{last.lower()}{suffix}@{domain}"


def generate_valid_row(idx: int) -> dict[str, str]:
    """Generate one valid candidate row."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    email = _random_email(first, last)
    phone = _random_phone()
    company = random.choice(COMPANIES)
    title = random.choice(TITLES)
    return {
        "name": name,
        "email": email,
        "phone": phone,
        "current_company": company,
        "title": title,
    }


def generate_edge_case_row(case_type: int) -> dict[str, str]:
    """Generate one edge-case candidate row."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    name = f"{first} {last}"
    base_email = _random_email(first, last)
    phone = _random_phone()

    case = case_type % 10

    if case == 0:
        # Missing email
        return {"name": name, "email": "", "phone": phone,
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 1:
        # Missing phone
        return {"name": name, "email": base_email, "phone": "",
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 2:
        # Missing name
        return {"name": "", "email": base_email, "phone": phone,
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 3:
        # Invalid phone (too short)
        return {"name": name, "email": base_email, "phone": "123",
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 4:
        # Invalid email
        return {"name": name, "email": "not-an-email", "phone": phone,
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 5:
        # All zeros phone
        return {"name": name, "email": base_email, "phone": "0000000000",
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 6:
        # Extra whitespace everywhere
        return {"name": f"  {name}  ", "email": f"  {base_email.upper()}  ",
                "phone": f"  {phone}  ",
                "current_company": f"  {random.choice(COMPANIES)}  ",
                "title": f"  {random.choice(TITLES)}  "}
    elif case == 7:
        # UPPERCASE email
        return {"name": name, "email": base_email.upper(), "phone": phone,
                "current_company": random.choice(COMPANIES), "title": random.choice(TITLES)}
    elif case == 8:
        # Missing company and title
        return {"name": name, "email": base_email, "phone": phone,
                "current_company": "", "title": ""}
    else:
        # Completely empty row
        return {"name": "", "email": "", "phone": "",
                "current_company": "", "title": ""}


def generate_stress_csv(
    output_path: Path,
    total_count: int = 10_000,
    valid_ratio: float = 0.9,
) -> tuple[int, int]:
    """Generate the stress test CSV file.

    Returns (valid_count, edge_case_count).
    """
    valid_count = int(total_count * valid_ratio)
    edge_count = total_count - valid_count

    rows: list[dict[str, str]] = []

    # Generate valid rows.
    for i in range(valid_count):
        rows.append(generate_valid_row(i))

    # Generate edge case rows.
    for i in range(edge_count):
        rows.append(generate_edge_case_row(i))

    # Add some intentional duplicates (copies of first 50 valid rows).
    duplicate_count = min(50, valid_count)
    for i in range(duplicate_count):
        rows.append(dict(rows[i]))

    # Shuffle so edge cases are distributed throughout.
    random.shuffle(rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "email", "phone", "current_company", "title"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} rows ({valid_count} valid + {edge_count} edge cases + {duplicate_count} duplicates)")
    print(f"Output: {output_path}")
    return valid_count, edge_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate stress test CSV for pipeline benchmarking")
    parser.add_argument("--output", default="input/candidate_10000.csv", help="Output CSV path")
    parser.add_argument("--count", type=int, default=10_000, help="Total row count (default: 10000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    random.seed(args.seed)
    generate_stress_csv(Path(args.output), total_count=args.count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
