from chains.numeric_utils import extract_normalized_facts, fact_survives


def test_currency_lakh_equivalence():
    a = extract_normalized_facts("₹2,00,000 per annum")
    b = extract_normalized_facts("2 lakh rupees a year")
    assert a and b
    assert a[0].normalized == b[0].normalized == "INR:200000.00"


def test_crore_scaling():
    facts = extract_normalized_facts("1.5 crore")
    assert facts[0].normalized == "INR:15000000.00"


def test_percent():
    facts = extract_normalized_facts("40% disability")
    assert facts[0].kind == "percent"
    assert facts[0].normalized == "PCT:40.00"


def test_date_equivalence_word_and_numeric():
    a = extract_normalized_facts("31 March 2026")
    b = extract_normalized_facts("31/03/2026")
    assert a and b
    assert a[0].normalized == b[0].normalized == "DATE:2026-03-31"


def test_fact_survives_numeric_true():
    survived, reason = fact_survives(
        "₹2,00,000 per annum",
        "Your family income must be below 2 lakh rupees every year to qualify.",
    )
    assert survived, reason


def test_fact_survives_numeric_false_when_dropped():
    survived, reason = fact_survives(
        "₹2,00,000 per annum",
        "There is an income limit to qualify for this scheme.",
    )
    assert not survived


def test_fact_survives_categorical_paraphrase():
    survived, reason = fact_survives(
        "Scheduled Caste",
        "This scheme is only for people from the Scheduled Caste community.",
    )
    assert survived, reason


def test_fact_survives_categorical_dropped():
    survived, reason = fact_survives(
        "Scheduled Caste",
        "This scheme is open to everyone regardless of background.",
    )
    assert not survived
