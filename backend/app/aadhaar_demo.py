"""
Simulated UIDAI/Aadhaar layer for the NoBar demo.

The real UIDAI authentication API requires an AUA/KUA licence and hardware
tokens, which is out of scope for a hackathon. Everything here is a local,
deterministic stand-in:

  * OTPs are fixed at DEMO_OTP ("123456") — the frontend shows this on screen.
  * "Fetching details" returns a stable citizen profile derived from known
    demo numbers, or a deterministic pseudo-profile seeded from the number, so
    any valid 12-digit Aadhaar resolves to the SAME person on every call.

To go to production, replace `fetch_aadhaar_details` with the real UIDAI
e-KYC/OTP API and stop returning OTPs in API responses. The rest of the app
only depends on the returned citizen dict, so integration is a drop-in swap.
"""

from __future__ import annotations

import random

from app.security import mask_aadhaar, normalize_aadhaar

__all__ = ["DEMO_OTP", "fetch_aadhaar_details", "otp_matches"]

DEMO_OTP = "123456"

_FIRST_NAMES = [
    "Asha", "Rita", "Sunita", "Kavita", "Lakshmi", "Meena", "Savitri", "Gita",
    "Anjali", "Priya", "Neha", "Pooja", "Deepika", "Shalini", "Ramesh", "Suresh",
    "Rajesh", "Mahesh", "Vijay", "Sanjay", "Anil", "Rakesh", "Manoj", "Amit",
    "Muhammad", "Imran", "Farhan", "Vikram", "Harish", "Arjun",
]
_LAST_NAMES = [
    "Singh", "Kumari", "Devi", "Sharma", "Verma", "Patel", "Gupta", "Reddy",
    "Nair", "Das", "Dasgupta", "Bose", "Khan", "Iyer", "Rao", "Yadav", "Jha",
]
_CITIES = {
    "Uttar Pradesh": ["Varanasi", "Lucknow", "Kanpur", "Agra"],
    "Madhya Pradesh": ["Indore", "Bhopal", "Gwalior", "Jabalpur"],
    "Tamil Nadu": ["Madurai", "Coimbatore", "Salem", "Trichy"],
    "West Bengal": ["Kolkata", "Howrah", "Bardhaman", "Asansol"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala"],
}
_GENDERS = ["Female", "Male", "Female", "Male"]


# Renowned, easy-to-remember demo numbers that resolve to fixed citizens.
DEMO_CITIZENS = {
    "111122223333": {
        "full_name": "Asha Kumari Singh",
        "dob": "1954-07-12",
        "gender": "Female",
        "state": "Uttar Pradesh",
        "district": "Varanasi",
        "pincode": "221001",
    },
    "222222222222": {
        "full_name": "Rahul Verma",
        "dob": "1990-03-15",
        "gender": "Male",
        "state": "Madhya Pradesh",
        "district": "Indore",
        "pincode": "452001",
    },
    "333333333333": {
        "full_name": "Lakshmi Devi",
        "dob": "1963-11-02",
        "gender": "Female",
        "state": "Tamil Nadu",
        "district": "Madurai",
        "pincode": "625001",
    },
    "444444444444": {
        "full_name": "Mohammed Imran Khan",
        "dob": "1985-06-20",
        "gender": "Male",
        "state": "West Bengal",
        "district": "Kolkata",
        "pincode": "700001",
    },
}


def fetch_aadhaar_details(aadhaar: str) -> dict:
    """Return the citizen profile for an Aadhaar number (simulated e-KYC).

    Stable for a given number: the same 12-digit Aadhaar always resolves to the
    same person, so repeat logins hit the same account.
    """
    digits = normalize_aadhaar(aadhaar)
    if digits in DEMO_CITIZENS:
        return dict(DEMO_CITIZENS[digits])

    rng = random.Random(int(digits))
    state = rng.sample(list(_CITIES.keys()), 1)[0]
    return {
        "full_name": f"{rng.sample(_FIRST_NAMES, 1)[0]} {rng.sample(_LAST_NAMES, 1)[0]}",
        "dob": f"{rng.randint(1940, 2008)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "gender": rng.sample(_GENDERS, 1)[0],
        "state": state,
        "district": rng.sample(_CITIES[state], 1)[0],
        "pincode": f"{rng.randint(100001, 855126)}",
    }


def otp_matches(aadhaar: str, otp: str) -> bool:
    """Demo OTP check — accept exact match only. Swap for UIDAI OTP verify."""
    return (otp or "").strip() == DEMO_OTP and bool(normalize_aadhaar(aadhaar))


def aadhaar_summary(aadhaar: str) -> dict:
    """Small envelope used by the request-OTP endpoint."""
    return {
        "otp": DEMO_OTP,
        "demo": True,
        "masked_aadhaar": mask_aadhaar(aadhaar),
        "details": fetch_aadhaar_details(aadhaar),
    }