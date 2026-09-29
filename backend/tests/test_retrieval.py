from general_logic.retrieval import retrieve_sections


def test_retrieve_sections_prefers_title_matches() -> None:
    document = {
        "sections": [
            {
                "section_number": "7",
                "title": "Disposal of request",
                "content": "The public authority shall dispose of the request within the prescribed period.",
            },
            {
                "section_number": "8",
                "title": "Exemption from disclosure",
                "content": "Information may be withheld in the circumstances listed in this section.",
            },
        ]
    }

    results = retrieve_sections(document, "What is the disposal of a request?")

    assert results
    assert results[0]["section_number"] == "7"


def test_retrieve_sections_returns_empty_for_unrelated_question() -> None:
    document = {
        "sections": [
            {
                "section_number": "7",
                "title": "Disposal of request",
                "content": "The public authority shall dispose of the request within the prescribed period.",
            }
        ]
    }

    assert retrieve_sections(document, "How are elections conducted?") == []


def test_retrieve_sections_prioritizes_requested_section_number() -> None:
    document = {
        "sections": [
            {
                "section_number": "5",
                "title": "Notice",
                "content": "A notice must be given before processing personal data.",
            },
            {
                "section_number": "7",
                "title": "Rights of the data principal",
                "content": "The data principal may exercise the rights described in this section.",
            },
        ]
    }

    results = retrieve_sections(document, "Explain section 7")

    assert results
    assert results[0]["section_number"] == "7"


def test_retrieve_sections_uses_semantic_legal_term_similarity() -> None:
     document = {
         "sections": [
             {
                 "section_number": "7",
                 "title": "Disposal of request",
                 "content": "The authority shall provide information within the prescribed period.",
             },
             {
                 "section_number": "8",
                 "title": "Exemption from disclosure",
                 "content": "Information may be withheld in listed circumstances.",
             },
         ]
     }

     results = retrieve_sections(document, "What is the time limit for providing information?")

     assert results
     assert results[0]["section_number"] == "7"


def test_retrieve_sections_deduplicates_same_section() -> None:
     section = {
         "section_number": "7",
         "title": "Disposal of request",
         "content": "The authority shall dispose of the request.",
     }
     results = retrieve_sections({"sections": [section, dict(section)]}, "Explain section 7")

     assert len(results) == 1


def test_retrieve_sections_is_limited_to_the_selected_document() -> None:
     selected_document = {
         "sections": [
             {"section_number": "1", "title": "Definitions", "content": "Terms are defined here."}
         ]
     }
     other_document = {
         "sections": [
             {"section_number": "7", "title": "Disposal", "content": "Requests are disposed of promptly."}
         ]
     }

     results = retrieve_sections(selected_document, "What does section 7 say?")

     assert all(result["section_number"] != "7" for result in results)
     assert retrieve_sections(other_document, "What does section 7 say?")[0]["section_number"] == "7"


def test_retrieve_sections_applies_relevance_threshold() -> None:
     document = {
         "sections": [
             {"section_number": "1", "title": "Definitions", "content": "Terms are defined here."}
         ]
     }

     assert retrieve_sections(document, "How are elections conducted?") == []


def test_retrieve_sections_ignores_malformed_sections_and_sorts_scores() -> None:
     document = {
         "sections": [
             None,
             {},
             {"section_number": "2", "title": "Request", "content": "A request may be submitted."},
             {"section_number": "3", "title": "Request and appeal", "content": "A request may be appealed."},
         ]
     }

     results = retrieve_sections(document, "What is a request and appeal?")

     assert results
     assert all(results[index]["final_score"] >= results[index + 1]["final_score"] for index in range(len(results) - 1))
