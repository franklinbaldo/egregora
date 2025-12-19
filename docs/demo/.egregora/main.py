import os
import yaml
from pathlib import Path

def define_env(env):
    """
    This is the hook for defining variables, macros and filters

    - variables: the dictionary that contains the environment variables
    - macro: a decorator function, to define a macro.
    """

    @env.macro
    def get_authors_data(author_uuids):
        """
        Get author data for a list of UUIDs.
        Reads profiles from docs/profiles/*.md
        """
        if not author_uuids:
            return []

        # env.conf['docs_dir'] is absolute path to docs directory
        docs_dir = Path(env.conf['docs_dir'])
        profiles_dir = docs_dir / "profiles"

        authors_data = []

        # Ensure author_uuids is a list
        if isinstance(author_uuids, str):
            author_uuids = [author_uuids]

        for uuid in author_uuids:
            # Handle potential file extensions or paths in UUID (though unlikely)
            clean_uuid = Path(uuid).stem
            profile_path = profiles_dir / f"{clean_uuid}.md"

            if profile_path.exists():
                try:
                    content = profile_path.read_text(encoding='utf-8')
                    if content.startswith('---'):
                        # Extract frontmatter
                        parts = content.split('---', 2)
                        if len(parts) >= 3:
                            frontmatter = yaml.safe_load(parts[1])
                            # Add UUID to data if not present
                            if 'uuid' not in frontmatter:
                                frontmatter['uuid'] = clean_uuid
                            authors_data.append(frontmatter)
                except Exception as e:
                    print(f"Error reading profile {clean_uuid}: {e}")

        return authors_data