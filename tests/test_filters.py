
from src.semantic.deterministic_filters import effective_section, low_value_reason, infer_category_hint


def test_narrative_request_filtered():
    t = "A parte autora alega cobrança tributária indevida e requer providências judiciais."
    assert low_value_reason(t) == "narrative_or_argument"


def test_generic_law_filtered():
    t = "A legislação de regência contém regras gerais sobre prazos, competência e formação da relação processual."
    assert low_value_reason(t) == "narrative_or_argument"


def test_dispositive_not_filtered():
    t = "Intime-se a Fazenda Nacional para apresentar impugnação no prazo de 30 dias."
    assert low_value_reason(t) is None


def test_julgo_procedente_is_result():
    t = "JULGO PROCEDENTE o pedido para reconhecer o direito à restituição."
    assert infer_category_hint(t) == "resultado_julgamento"


def test_numbered_party_request_is_filtered_outside_dispositivo():
    t = "a) DETERMINE a remessa de todos os débitos da Impetrante para a PGFN."
    assert low_value_reason(t, section="DECISAO") == "likely_party_request"


def test_numbered_party_request_allowed_in_dispositivo_for_llm_review():
    t = "a) DETERMINE a remessa de todos os débitos da Impetrante para a PGFN."
    assert low_value_reason(t, section="DISPOSITIVO") is None


def test_ao_final_seja_julgado_is_party_request():
    t = "g) Ao final, seja julgado inteiramente procedente o pedido."
    assert low_value_reason(t, section="DECISAO") == "likely_party_request"


def test_historical_decision_reference_is_filtered():
    t = "Na sequência, a decisão de id. 98678120 reconheceu a conexão e determinou a redistribuição."
    assert low_value_reason(t, section="DECISAO") == "historical_reference"


def test_historical_indeferiu_se_id_is_filtered():
    t = "Indeferiu-se o pedido liminar no id. 98678258."
    assert low_value_reason(t, section="DECISAO") == "historical_reference"


def test_orphan_deadline_is_filtered():
    assert low_value_reason("Prazo 5 (cinco) dias.", section="DECISAO") == "orphan_deadline"


def test_generic_urgency_is_filtered():
    assert low_value_reason("Cumpra-se com urgência.", section="DECISAO") == "generic_command"


def test_remeta_trf_is_recurso():
    t = "Remeta-se o feito ao TRF5 em razão de sentença sujeita ao duplo grau de jurisdição obrigatório."
    assert infer_category_hint(t) == "recurso_proximo_passo"


def test_julgo_procedente_confirmo_liminar_is_result_not_tutela():
    t = "JULGO PROCEDENTE o pedido e confirmo a liminar inicialmente deferida."
    assert infer_category_hint(t) == "resultado_julgamento"


def test_denego_seguranca_is_result():
    t = "Ante o exposto, DENEGO A SEGURANÇA pleiteada, extinguindo o processo com resolução do mérito."
    assert infer_category_hint(t) == "resultado_julgamento"


def test_effective_section_promotes_clear_decisum():
    assert effective_section("Ante o exposto, denego a segurança.", "FUNDAMENTACAO") == "DISPOSITIVO"


def test_pure_numeric_identifier_is_filtered():
    t = "25111006294315100000147581491"
    assert low_value_reason(t, section="DISPOSITIVO") == "numeric_identifier_only"


def test_historical_dated_dispatch_is_filtered():
    t = (
        "Por meio de despacho datado de 26 de setembro de 2025 (Id. 119547292), "
        "este Juízo determinou a notificação da autoridade coatora para prestar informações."
    )
    assert low_value_reason(t, section="DECISAO") == "historical_reference"


def test_historical_this_court_past_tense_is_filtered():
    t = "No caso dos autos, este Juízo fundamentadamente denegou a segurança."
    assert low_value_reason(t, section="DECISAO") == "historical_reference"


def test_external_case_citation_is_filtered():
    t = (
        'Reconhece-se o direito do autor ao ressarcimento. '
        '(PROCESSO: 08134756420234058000, APELAÇÃO CÍVEL, '
        'DESEMBARGADOR FEDERAL FULANO, 4ª TURMA, JULGAMENTO: 24/09/2024).'
    )
    assert low_value_reason(t, section="DECISAO") == "external_case_citation"


def test_roman_parenthesized_final_request_is_filtered():
    t = (
        "(ii) ao final, o reconhecimento do direito adquirido à fruição integral "
        "do benefício fiscal e à compensação dos valores recolhidos."
    )
    assert low_value_reason(t, section="DECISAO") == "likely_party_request"


def test_infinitive_numbered_request_is_filtered():
    t = "c) Determinar que qualquer procedimento de cobrança somente seja iniciado após a impugnação."
    assert low_value_reason(t, section="DECISAO") == "likely_party_request"


def test_named_orphan_deadline_is_filtered():
    t = "Prazo para impugnação: 05 (cinco) dias."
    assert low_value_reason(t, section="OUTRO") == "orphan_deadline"


def test_dispositive_heading_with_colon_is_incomplete():
    t = "Ante o exposto, DETERMINO, com urgência:"
    assert low_value_reason(t, section="DISPOSITIVO") == "trailing_colon_fragment"


def test_cite_se_is_intimation_not_deadline():
    t = "Cite-se a União, por intermédio da Procuradoria da Fazenda Nacional."
    assert infer_category_hint(t) == "intimacao_manifestacao"


def test_retifique_se_is_order():
    t = "Retifique-se a autuação para a classe Cautelar Fiscal."
    assert infer_category_hint(t) == "ordem_determinacao"


def test_encaminhe_se_contadoria_is_order_even_with_parecer():
    t = "Assim, encaminhe-se o feito à Contadoria Judicial para conferência e parecer."
    assert infer_category_hint(t) == "ordem_determinacao"
