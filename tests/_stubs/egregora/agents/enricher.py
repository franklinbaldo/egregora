class EnrichmentAgent:
    pass


def create_url_enrichment_agent(model=None, _simple=True):
    return EnrichmentAgent()


def create_media_enrichment_agent(model=None, _simple=True):
    return EnrichmentAgent()


def run_url_enrichment_agent(agent, url, prompts_dir=None):
    return "stub url enrichment"


def run_media_enrichment_agent(agent, media_path, **kwargs):
    return "stub media enrichment"
