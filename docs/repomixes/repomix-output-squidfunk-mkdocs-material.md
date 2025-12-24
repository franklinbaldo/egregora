This file is a merged representation of a subset of the codebase, containing specifically included files, combined into a single document by Repomix.
The content has been processed where security check has been disabled.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Only files matching these patterns are included: docs/*
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Security check has been disabled - content may contain sensitive information
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
docs/
  alternatives.md
  browser-support.md
  conventions.md
  creating-your-site.md
  customization.md
  getting-started.md
  index.md
  license.md
  philosophy.md
  publishing-your-site.md
  schema.json
  upgrade.md
```

# Files

## File: docs/alternatives.md
````markdown
# Alternatives

There are tons of static site generators and themes out there and choosing the
right one for your tech stack is a tough decision. If you're unsure if Material
for MkDocs is the right solution for you, this section should help you evaluate
alternative solutions.

## Docusaurus

[Docusaurus] by Facebook is a very popular documentation generator and a good
choice if you or your company are already using [React] to build your site.
It will generate a [single page application] which is fundamentally different
from the site Material for MkDocs generates for you.

__Advantages__

- Very powerful, customizable and extendable
- Provides many components that aid in technical writing
- Large and rich ecosystem, backed by Facebook

__Challenges__

- High learning curve, JavaScript knowledge mandatory
- JavaScript ecosystem is very volatile, rather high maintenance
- More time needed to get up and running

While [Docusaurus] is one of the best choices when it comes to documentation
sites that output a single page application, there are many more solutions,
including [Docz], [Gatsby], [Vuepress] and [Docsify] that approach
this problem similarly.

  [Docusaurus]: https://docusaurus.io/
  [React]: https://reactjs.org/
  [single page application]: https://en.wikipedia.org/wiki/Single-page_application
  [Docz]: https://www.docz.site/
  [Gatsby]: https://www.gatsbyjs.com/
  [VuePress]: https://vuepress.vuejs.org/
  [Docsify]: https://docsify.js.org/

## Jekyll

[Jekyll] is probably one of the most mature and widespread static site
generators and is written in [Ruby]. It is not specifically geared towards
technical project documentation and has many themes to choose from, which
can be challenging.

__Advantages__

- Battle-tested, rich ecosystem, many themes to choose from
- Brings great capabilities for blogging  (permalinks, tags, etc.)
- Generates a SEO-friendly site, similar to Material for MkDocs

__Challenges__

- Not specifically geared towards technical project documentation
- Limited Markdown capabilities, not as advanced as Python Markdown
- More time needed to get up and running

  [Jekyll]: https://jekyllrb.com/
  [Ruby]: https://www.ruby-lang.org/de/

## Sphinx

[Sphinx] is an alternative static site generator specifically geared towards
generating reference documentation, offering powerful capabilities that are
lacking in MkDocs. It uses [reStructured text], a format similar to Markdown,
which some users find harder to use.

__Advantages__

- Very powerful, customizable and extendable
- Generates reference documentation from [Python docstrings]
- Large and rich ecosystem, used by many Python projects

__Challenges__

- High learning curve, [reStructured text] syntax might be challenging
- Search is less powerful than the one provided by MkDocs
- More time needed to get up and running

If you're considering using Sphinx because you need to generate reference
documentation, you should give [mkdocstrings] a try – an actively maintained
and popular framework building on top of MkDocs, implementing Sphinx-like
functionality.

  [Sphinx]: https://www.sphinx-doc.org/
  [reStructured text]: https://en.wikipedia.org/wiki/ReStructuredText
  [Python docstrings]: https://www.python.org/dev/peps/pep-0257/
  [mkdocstrings]: https://github.com/mkdocstrings/mkdocstrings

## GitBook

[GitBook] offers a hosted documentation solution that generates a beautiful and
functional site from Markdown files in your GitHub repository. However, it was
once Open Source, but turned into a closed source solution some time ago.

__Advantages__

- Hosted solution, minimal technical knowledge required
- Custom domains, authentication and other enterprise features
- Great collaboration features for teams

__Challenges__

- Closed source, not free for proprietary projects
- Limited Markdown capabilities, not as advanced as Python Markdown
- Many Open Source projects moved away from GitBook

Many users switched from [GitBook] to Material for MkDocs, as they want to keep
control and ownership of their documentation, favoring an Open Source solution.

  [GitBook]: https://www.gitbook.com/
````

## File: docs/browser-support.md
````markdown
# Browser support

Material for MkDocs goes at great lengths to support the largest possible range
of browsers while retaining the simplest possibilities for customization via
modern CSS features like [custom properties] and [mask images].

  [custom properties]: https://caniuse.com/css-variables
  [mask images]: https://caniuse.com/mdn-css_properties_mask-image

## Supported browsers

The following table lists all browsers for which Material for MkDocs offers full
support, so it can be assumed that all features work without degradation. If you
find that something doesn't look right in a browser which is in the supported
version range, please [open an issue]:

<figure markdown>

| Browser                              | Version | Release date |         |        |      Usage |
| ------------------------------------ | ------: | -----------: | ------: | -----: | ---------: |
|                                      |         |              | desktop | mobile |    overall |
| :fontawesome-brands-chrome: Chrome   |     49+ |      03/2016 | 25.65%  | 38.33% |     63.98% |
| :fontawesome-brands-safari: Safari   |     10+ |      09/2016 |  4.63%  | 14.96% |     19.59% |
| :fontawesome-brands-edge: Edge       |     79+ |      01/2020 |  3.95%  |    n/a |      3.95% |
| :fontawesome-brands-firefox: Firefox |     53+ |      04/2017 |  3.40%  |   .30% |      3.70% |
| :fontawesome-brands-opera: Opera     |     36+ |      03/2016 |  1.44%  |   .01% |      1.45% |
|                                      |         |              |         |        | __92.67%__ |

  <figcaption markdown>

Browser support matrix sourced from [caniuse.com].[^1]

  </figcaption>
</figure>

  [^1]:
    The data was collected from [caniuse.com] in January 2022, and is primarily
    based on browser support for [custom properties], [mask images] and the
    [:is pseudo selector] which are not entirely polyfillable. Browsers with a
    cumulated market share of less than 1% were not considered, but might still
    be fully or partially supported.

Note that the usage data is based on global browser market share, so it could
in fact be entirely different for your target demographic. It's a good idea to
check the distribution of browser types and versions among your users.

  [open an issue]: https://github.com/squidfunk/mkdocs-material/issues/new/choose
  [caniuse.com]: https://caniuse.com/
  [:is pseudo selector]: https://caniuse.com/css-matches-pseudo
  [browser support]: #supported-browsers
  [built-in privacy plugin]: plugins/privacy.md

## Other browsers

Albeit your site might not look as perfect as when viewed with a modern browser,
the following older browser versions might work with some additional effort:

- :fontawesome-brands-firefox: __Firefox 31-52__ – icons will render as little
  boxes due to missing support for [mask images]. While this cannot be
  polyfilled, it might be mitigated by hiding the icons altogether.
- :fontawesome-brands-edge: __Edge 16-18__ – the spacing of some elements might
  be a little off due to missing support for the [:is pseudo selector], which
  can be mitigated with some additional effort.
- :fontawesome-brands-internet-explorer: __Internet Explorer__ - no support,
  mainly due to missing support for [custom properties]. The last version of
  Material for MkDocs to support Internet Explorer is
  <!-- md:version 4.6.3 -->.
````

## File: docs/conventions.md
````markdown
# Conventions

This section explains several conventions used in this documentation.

## Symbols

This documentation use some symbols for illustration purposes. Before you read
on, please make sure you've made yourself familiar with the following list of
conventions:

### <!-- md:version --> – Version { data-toc-label="Version" }

The tag symbol in conjunction with a version number denotes when a specific
feature or behavior was added. Make sure you're at least on this version
if you want to use it.

### <!-- md:default --> – Default value { #default data-toc-label="Default value" }

Some properties in `mkdocs.yml` have default values for when the author does not
explicitly define them. The default value of the property is always included.

#### <!-- md:default computed --> – Default value is computed { #default data-toc-label="is computed" }

Some default values are not set to static values but computed from other values,
like the site language, repository provider, or other settings.

#### <!-- md:default none --> – Default value is empty { #default data-toc-label="is empty" }

Some properties do not contain default values. This means that the functionality
that is associated with them is not available unless explicitly enabled.

### <!-- md:flag metadata --> – Metadata property { #metadata data-toc-label="Metadata property" }

This symbol denotes that the thing described is a metadata property, which can
be used in Markdown documents as part of the front matter definition.

### <!-- md:flag multiple --> – Multiple instances { #multiple-instances data-toc-label="Multiple instances" }

This symbol denotes that the plugin supports multiple instances, i.e, that it
can be used multiple times in the `plugins` setting in `mkdocs.yml`.

### <!-- md:feature --> – Optional feature { #feature data-toc-label="Optional feature" }

Most of the features are hidden behind feature flags, which means they must
be explicitly enabled via `mkdocs.yml`. This allows for the existence of
potentially orthogonal features.

### <!-- md:flag experimental --> – Experimental { data-toc-label="Experimental" }

Some newer features are still considered experimental, which means they might
(although rarely) change at any time, including their complete removal (which
hasn't happened yet).

### <!-- md:plugin --> – Plugin { data-toc-label="Plugin" }

Several features are implemented through MkDocs excellent plugin architecture,
some of which are built-in and distributed with Material for MkDocs, so no
installation is required.

### <!-- md:extension --> – Markdown extension { data-toc-label="Markdown extension" #extension }

This symbol denotes that the thing described is a Markdown extension, which can
be enabled in `mkdocs.yml` and adds additional functionality to the Markdown
parser.

### <!-- md:flag required --> – Required value { #required data-toc-label="Required value" }

Some (very few in fact) properties or settings are required, which means the
authors must explicitly define them.

### <!-- md:flag customization --> – Customization { #customization data-toc-label="Customization" }

This symbol denotes that the thing described is a customization that must be
added by the author.

### <!-- md:utility --> – Utility { data-toc-label="Utility" }

Besides plugins, there are some utilities that build on top of MkDocs in order
to provide extended functionality, like for example support for versioning.
````

## File: docs/creating-your-site.md
````markdown
# Creating your site

After you've [installed] Material for MkDocs, you can bootstrap your project
documentation using the `mkdocs` executable. Go to the directory where you want
your project to be located and enter:

```
mkdocs new .
```

Alternatively, if you're running Material for MkDocs from within Docker, use:

=== "Unix, Powershell"

    ```
    docker run --rm -it -v ${PWD}:/docs squidfunk/mkdocs-material new .
    ```

=== "Windows (cmd)"

    ```
    docker run --rm -it -v "%cd%":/docs squidfunk/mkdocs-material new .
    ```

This will create the following structure:

``` { .sh .no-copy }
.
├─ docs/
│  └─ index.md
└─ mkdocs.yml
```

  [installed]: getting-started.md

## Configuration

### Minimal configuration

Simply set the `site_name` and add the following lines to `mkdocs.yml` to enable the theme:

``` yaml hl_lines="2-5"
site_name: My site
site_url: https://mydomain.org/mysite
theme:
  name: material
```

The `site_url` setting is important for a number of reasons.
By default, MkDocs will assume that your site is hosted at the root of
your domain. This is not the case, for example, when [publishing to GitHub
pages] - unless you use a custom domain. Another reason is that some of the
plugins require the `site_url` to be set, so you should always do this.

  [publishing to GitHub pages]: publishing-your-site.md#github-pages
  [installation methods]: getting-started.md#installation

???+ tip "Recommended: [configuration validation and auto-complete]"

    In order to minimize friction and maximize productivity, Material for MkDocs
    provides its own [schema.json][^1] for `mkdocs.yml`. If your editor supports
    YAML schema validation, it's definitely recommended to set it up:

    === "Visual Studio Code"

        1.  Install [`vscode-yaml`][vscode-yaml] for YAML language support.
        2.  Add the schema under the `yaml.schemas` key in your user or
            workspace [`settings.json`][settings.json]:

            ``` json
            {
              "yaml.schemas": {
                "https://squidfunk.github.io/mkdocs-material/schema.json": "mkdocs.yml"
              },
              "yaml.customTags": [ // (1)!
                "!ENV scalar",
                "!ENV sequence",
                "!relative scalar",
                "tag:yaml.org,2002:python/name:material.extensions.emoji.to_svg",
                "tag:yaml.org,2002:python/name:material.extensions.emoji.twemoji",
                "tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format",
                "tag:yaml.org,2002:python/object/apply:pymdownx.slugs.slugify mapping"
              ]
            }
            ```

            1.  This setting is necessary if you plan to use [icons and emojis],
                or Visual Studio Code will show errors on certain lines.

    === "Other"

        1.  Ensure your editor of choice has support for YAML schema validation.
        2.  Add the following lines at the top of `mkdocs.yml`:

            ``` yaml
            # yaml-language-server: $schema=https://squidfunk.github.io/mkdocs-material/schema.json
            ```

  [^1]:
    If you're a MkDocs plugin or Markdown extension author and your project
    works with Material for MkDocs, you're very much invited to contribute a
    schema for your [extension] or [plugin] as part of a pull request on GitHub.
    If you already have a schema defined, or wish to self-host your schema to
    reduce duplication, you can add it via [$ref].

  [configuration validation and auto-complete]: https://x.com/squidfunk/status/1487746003692400642
  [schema.json]: schema.json
  [vscode-yaml]: https://marketplace.visualstudio.com/items?itemName=redhat.vscode-yaml
  [settings.json]: https://code.visualstudio.com/docs/getstarted/settings
  [extension]: https://github.com/squidfunk/mkdocs-material/tree/master/docs/schema/extensions
  [plugin]: https://github.com/squidfunk/mkdocs-material/tree/master/docs/schema/plugins
  [$ref]: https://json-schema.org/understanding-json-schema/structuring.html#ref
  [icons and emojis]: reference/icons-emojis.md

### Advanced configuration

Material for MkDocs comes with many configuration options. The setup section
explains in great detail how to configure and customize colors, fonts, icons
and much more:

<div class="mdx-columns" markdown>

- [Changing the colors]
- [Changing the fonts]
- [Changing the language]
- [Changing the logo and icons]
- [Ensuring data privacy]
- [Setting up navigation]
- [Setting up site search]
- [Setting up site analytics]
- [Setting up social cards]
- [Setting up a blog]
- [Setting up tags]
- [Setting up versioning]
- [Setting up the header]
- [Setting up the footer]
- [Adding a git repository]
- [Adding a comment system]
- [Building an optimized site]
- [Building for offline usage]

</div>

Furthermore, see the list of supported [Markdown extensions] that are natively
integrated with Material for MkDocs, delivering an unprecedented low-effort
technical writing experience.

  [Changing the colors]: setup/changing-the-colors.md
  [Changing the fonts]: setup/changing-the-fonts.md
  [Changing the language]: setup/changing-the-language.md
  [Changing the logo and icons]: setup/changing-the-logo-and-icons.md
  [Ensuring data privacy]: setup/ensuring-data-privacy.md
  [Setting up navigation]: setup/setting-up-navigation.md
  [Setting up site search]: setup/setting-up-site-search.md
  [Setting up site analytics]: setup/setting-up-site-analytics.md
  [Setting up social cards]: setup/setting-up-social-cards.md
  [Setting up a blog]: setup/setting-up-a-blog.md
  [Setting up tags]: setup/setting-up-tags.md
  [Setting up versioning]: setup/setting-up-versioning.md
  [Setting up the header]: setup/setting-up-the-header.md
  [Setting up the footer]: setup/setting-up-the-footer.md
  [Adding a git repository]: setup/adding-a-git-repository.md
  [Adding a comment system]: setup/adding-a-comment-system.md
  [Building for offline usage]: setup/building-for-offline-usage.md
  [Building an optimized site]: setup/building-an-optimized-site.md
  [Markdown extensions]: setup/extensions/index.md

## Templates

If you want to jump start a new project, you can use one of our growing
collection of templates:

<div class="grid cards" markdown>

-   :octicons-repo-template-24: &nbsp; __[Blog][blog-template]__

    ---

    Create a blog

-   :octicons-repo-template-24: &nbsp; __[Social cards][social-cards-template]__

    ---

    Create documentation with social cards

</div>

[blog-template]: https://github.com/mkdocs-material/create-blog
[social-cards-template]: https://github.com/mkdocs-material/create-social-cards

## Previewing as you write

MkDocs includes a live preview server, so you can preview your changes as you
write your documentation. The server will automatically rebuild the site upon
saving. Start it with:

``` sh
mkdocs serve # (1)!
```

1.  If you have a large documentation project, it might take minutes until
    MkDocs has rebuilt all pages for you to preview. If you're only interested
    in the current page, the [`--dirtyreload`][--dirtyreload] flag will make
    rebuilds much faster:

    ```
    mkdocs serve --dirtyreload
    ```

If you're running Material for MkDocs from within Docker, use:

=== "Unix, Powershell"

    ```
    docker run --rm -it -p 8000:8000 -v ${PWD}:/docs squidfunk/mkdocs-material
    ```

=== "Windows"

    ```
    docker run --rm -it -p 8000:8000 -v "%cd%":/docs squidfunk/mkdocs-material
    ```

Point your browser to [localhost:8000][live preview] and you should see:

[![Creating your site]][Creating your site]

  [--dirtyreload]: https://www.mkdocs.org/about/release-notes/#support-for-dirty-builds-990
  [live preview]: http://localhost:8000
  [Creating your site]: assets/screenshots/creating-your-site.png

## Building your site

When you're finished editing, you can build a static site from your Markdown
files with:

```
mkdocs build
```

If you're running Material for MkDocs from within Docker, use:

=== "Unix, Powershell"

    ```
    docker run --rm -it -v ${PWD}:/docs squidfunk/mkdocs-material build
    ```

=== "Windows"

    ```
    docker run --rm -it -v "%cd%":/docs squidfunk/mkdocs-material build
    ```

The contents of this directory make up your project documentation. There's no
need for operating a database or server, as it is completely self-contained.
The site can be hosted on [GitHub Pages], [GitLab Pages], a CDN of your choice
or your private web space.

  [GitHub Pages]: publishing-your-site.md#github-pages
  [GitLab pages]: publishing-your-site.md#gitlab-pages

If you intend to distribute your documentation as a set of files to be
read from a local filesystem rather than a web server (such as in a
`.zip` file), please read the notes about [building for offline
usage].

  [building for offline usage]: setup/building-for-offline-usage.md
````

## File: docs/customization.md
````markdown
# Customization

Project documentation is as diverse as the projects themselves and Material for
MkDocs is a great starting point for making it look beautiful. However, as you
write your documentation, you may reach a point where small adjustments are
necessary to preserve your brand's style.

## Adding assets

[MkDocs] provides several ways to customize a theme. In order to make a few
small tweaks to Material for MkDocs, you can just add CSS and JavaScript files to
the `docs` directory.

  [MkDocs]: https://www.mkdocs.org

### Additional CSS

If you want to tweak some colors or change the spacing of certain elements,
you can do this in a separate style sheet. The easiest way is by creating a
new style sheet file in the `docs` directory:

``` { .sh .no-copy }
.
├─ docs/
│  └─ stylesheets/
│     └─ extra.css
└─ mkdocs.yml
```

Then, add the following lines to `mkdocs.yml`:

``` yaml
extra_css:
  - stylesheets/extra.css
```

### Additional JavaScript

If you want to integrate another syntax highlighter or add some custom logic to
your theme, create a new JavaScript file in the `docs` directory:

``` { .sh .no-copy }
.
├─ docs/
│  └─ javascripts/
│     └─ extra.js
└─ mkdocs.yml
```

Then, add the following lines to `mkdocs.yml`:

``` yaml
extra_javascript:
  - javascripts/extra.js
```

??? tip "How to integrate with third-party JavaScript libraries"

    It is likely that you will want to run your JavaScript code only
    once the page has been fully loaded by the browser. This means
    installing a callback function subscribing to events on the
    `document$` observable exported by Material for MkDocs.
    Using the `document$` observable is particularly important if you
    are using [instant loading] since it will not result in a page
    refresh in the browser - but subscribers on the observable will be
    notified.

    ``` javascript
    document$.subscribe(function() {
      console.log("Initialize third-party libraries here")
    })
    ```

    `document$` is an [RxJS Observable] and you can call the `subscribe()`
    method any number of times to attach different functionality.

  [instant loading]: setup/setting-up-navigation.md/#instant-loading
  [RxJS Observable]: https://rxjs.dev/api/index/class/Observable

## Extending the theme

If you want to alter the HTML source (e.g. add or remove some parts), you can
extend the theme. MkDocs supports [theme extension], an easy way to override
parts of Material for MkDocs without forking from git. This ensures that you
can update to the latest version more easily.

  [theme extension]: https://www.mkdocs.org/user-guide/customizing-your-theme/#using-the-theme-custom_dir

### Setup and theme structure

Enable Material for MkDocs as usual in `mkdocs.yml`, and create a new folder
for `overrides` which you then reference using the [`custom_dir`][custom_dir]
setting:

``` yaml
theme:
  name: material
  custom_dir: overrides
```

!!! warning "Theme extension prerequisites"

    As the [`custom_dir`][custom_dir] setting is used for the theme extension
    process, Material for MkDocs needs to be installed via `pip` and referenced
    with the [`name`][name] setting in `mkdocs.yml`. It will not work when
    cloning from `git`.

The structure in the `overrides` directory must mirror the directory structure
of the original theme, as any file in the `overrides` directory will replace the
file with the same name which is part of the original theme. Besides, further
assets may also be put in the `overrides` directory:

``` { .sh .no-copy }
.
├─ .icons/                             # Bundled icon sets
├─ assets/
│  ├─ images/                          # Images and icons
│  ├─ javascripts/                     # JavaScript files
│  └─ stylesheets/                     # Style sheets
├─ partials/
│  ├─ integrations/                    # Third-party integrations
│  │  ├─ analytics/                    # Analytics integrations
│  │  └─ analytics.html                # Analytics setup
│  ├─ languages/                       # Translation languages
│  ├─ actions.html                     # Actions
│  ├─ alternate.html                   # Site language selector
│  ├─ comments.html                    # Comment system (empty by default)
│  ├─ consent.html                     # Consent
│  ├─ content.html                     # Page content
│  ├─ copyright.html                   # Copyright and theme information
│  ├─ feedback.html                    # Was this page helpful?
│  ├─ footer.html                      # Footer bar
│  ├─ header.html                      # Header bar
│  ├─ icons.html                       # Custom icons
│  ├─ language.html                    # Translation setup
│  ├─ logo.html                        # Logo in header and sidebar
│  ├─ nav.html                         # Main navigation
│  ├─ nav-item.html                    # Main navigation item
│  ├─ pagination.html                  # Pagination (used for blog)
│  ├─ palette.html                     # Color palette toggle
│  ├─ post.html                        # Blog post excerpt
│  ├─ progress.html                    # Progress indicator
│  ├─ search.html                      # Search interface
│  ├─ social.html                      # Social links
│  ├─ source.html                      # Repository information
│  ├─ source-file.html                 # Source file information
│  ├─ tabs.html                        # Tabs navigation
│  ├─ tabs-item.html                   # Tabs navigation item
│  ├─ tags.html                        # Tags
│  ├─ toc.html                         # Table of contents
│  ├─ toc-item.html                    # Table of contents item
│  └─ top.html                         # Back-to-top button
├─ 404.html                            # 404 error page
├─ base.html                           # Base template
├─ blog.html                           # Blog index page
├─ blog-archive.html                   # Blog archive index page
├─ blog-category.html                  # Blog category index page
├─ blog-post.html                      # Blog post page
└─ main.html                           # Default page
```

  [custom_dir]: https://www.mkdocs.org/user-guide/configuration/#custom_dir
  [name]: https://www.mkdocs.org/user-guide/configuration/#name

### Overriding partials

In order to override a partial, we can replace it with a file of the same name
and location in the `overrides` directory. For example, to replace the original
`footer.html` partial, create a new `footer.html` partial in the `overrides`
directory:

``` { .sh .no-copy }
.
├─ overrides/
│  └─ partials/
│     └─ footer.html
└─ mkdocs.yml
```

MkDocs will now use the new partial when rendering the theme. This can be done
with any file.

### Overriding blocks <small>recommended</small> { #overriding-blocks data-toc-label="Overriding blocks" }

Besides overriding partials, it's also possible to override (and extend)
template blocks, which are defined inside the templates and wrap specific
features. In order to set up block overrides, create a `main.html` file inside
the `overrides` directory:

``` { .sh .no-copy }
.
├─ overrides/
│  └─ main.html
└─ mkdocs.yml
```

Then, e.g. to override the site title, add the following lines to `main.html`:

``` html
{% extends "base.html" %}

{% block htmltitle %}
  <title>Lorem ipsum dolor sit amet</title>
{% endblock %}
```

If you intend to __add__ something to a block rather than to replace it
altogether with new content, use `{{ super() }}` inside the block to include the
original block content. This is particularly useful when adding third-party
scripts to your docs, e.g.

``` html
{% extends "base.html" %}

{% block scripts %}
  <!-- Add scripts that need to run before here -->
  {{ super() }}
  <!-- Add scripts that need to run afterwards here -->
{% endblock %}
```

The following template blocks are provided by the theme:

| Block name        | Purpose                                         |
| :---------------- | :---------------------------------------------- |
| `analytics`       | Wraps the Google Analytics integration          |
| `announce`        | Wraps the announcement bar                      |
| `config`          | Wraps the JavaScript application config         |
| `container`       | Wraps the main content container                |
| `content`         | Wraps the main content                          |
| `extrahead`       | Empty block to add custom meta tags             |
| `fonts`           | Wraps the font definitions                      |
| `footer`          | Wraps the footer with navigation and copyright  |
| `header`          | Wraps the fixed header bar                      |
| `hero`            | Wraps the hero teaser (if available)            |
| `htmltitle`       | Wraps the `<title>` tag                         |
| `libs`            | Wraps the JavaScript libraries (header)         |
| `outdated`        | Wraps the version warning                       |
| `scripts`         | Wraps the JavaScript application (footer)       |
| `site_meta`       | Wraps the meta tags in the document head        |
| `site_nav`        | Wraps the site navigation and table of contents |
| `styles`          | Wraps the style sheets (also extra sources)     |
| `tabs`            | Wraps the tabs navigation (if available)        |

## Theme development

Material for MkDocs is built on top of [TypeScript], [RxJS] and [SASS], and
uses a lean, custom build process to put everything together.[^1] If you want
to make more fundamental changes, it may be necessary to make the adjustments
directly in the source of the theme and recompile it.

  [^1]:
    Prior to <!-- md:version 7.0.0 --> the build was based on Webpack, resulting
    in occasional broken builds due to incompatibilities with loaders and
    plugins. Therefore, we decided to swap Webpack for a leaner solution which
    is now based on [RxJS] as the application itself. This allowed for the
    pruning of more than 500 dependencies (~30% less).

  [TypeScript]: https://www.typescriptlang.org/
  [RxJS]: https://github.com/ReactiveX/rxjs
  [SASS]: https://sass-lang.com

### Environment setup

First, clone the repository:

```
git clone https://github.com/squidfunk/mkdocs-material
cd mkdocs-material
```

Next, create a new [Python virtual environment][venv] and
[activate][venv-activate] it:

```
python -m venv venv
source venv/bin/activate
```

!!! note "Ensure pip always runs in a virtual environment"

    If you set the environment variable `PIP_REQUIRE_VIRTUALENV` to
    `true`, `pip` will refuse to install anything outside a virtual
    environment. Forgetting to activate a `venv` can be very annoying
    as it will install all sorts of things outside virtual
    environments over time, possibly leading to further errors. So,
    you may want to add this to your `.bashrc` or `.zshrc` and
    re-start your shell:

    ```
    export PIP_REQUIRE_VIRTUALENV=true
    ```

  [venv]: https://docs.python.org/3/library/venv.html
  [venv-activate]: https://docs.python.org/3/library/venv.html#how-venvs-work

Then, install all Python dependencies:

```
pip install -e ".[git, recommended, imaging]"
pip install nodeenv
```

In addition, you will need to install the `cairo` and `pngquant` libraries in your
system, as described in the [image processing] requirements guide.

[image processing]: plugins/requirements/image-processing.md

Finally, install the [Node.js] LTS version into the Python virtual environment
and install all Node.js dependencies:

```
nodeenv -p -n lts
npm install
```

  [Node.js]: https://nodejs.org

### Development mode

Start the watcher with:

```
npm start
```

Then, in a second terminal window, start the MkDocs live preview server with:

```
mkdocs serve --watch-theme
```

Point your browser to [localhost:8000][live preview] and you should see this
very documentation in front of you.

!!! warning "Automatically generated files"

    Never make any changes in the `material` directory, as the contents of this
    directory are automatically generated from the `src` directory and will be
    overwritten when the theme is built.

  [live preview]: http://localhost:8000

### Building the theme

When you're finished making your changes, you can build the theme by invoking:

``` sh
npm run build # (1)!
```

1.  While this command will build all theme files, it will skip the overrides
    used in Material for MkDocs' own documentation which are not distributed
    with the theme. If you forked the theme and want to build the overrides
    as well, e.g. before submitting a PR with changes, use:

    ```
    npm run build:all
    ```

    This will take longer, as now the icon search index, schema files, as
    well as additional style sheet and JavaScript files are built.

This triggers the production-level compilation and minification of all style
sheets and JavaScript files. After the command exits, the compiled files are
located in the `material` directory. When running `mkdocs build`, you should
now see your changes to the original theme.
````

## File: docs/getting-started.md
````markdown
# Getting started

Material for MkDocs is a powerful documentation framework on top of [MkDocs],
a static site generator for project documentation.[^1] If you're familiar with
Python, you can install Material for MkDocs with [`pip`][pip], the Python
package manager. If not, we recommend using [`docker`][docker].

  [^1]:
    In 2016, Material for MkDocs started out as a simple theme for MkDocs, but
    over the course of several years, it's now much more than that – with the
    many built-in plugins, settings, and countless customization abilities,
    Material for MkDocs is now one of the simplest and most powerful frameworks
    for creating documentation for your project.

  [MkDocs]: https://www.mkdocs.org
  [pip]: #with-pip
  [docker]: #with-docker

## Installation

### with pip <small>recommended</small> { #with-pip data-toc-label="with pip" }

Material for MkDocs is published as a [Python package] and can be installed with
`pip`, ideally by using a [virtual environment]. Open up a terminal and install
Material for MkDocs with:

=== "Latest"

    ``` sh
    pip install mkdocs-material
    ```

=== "9.x"

    ``` sh
    pip install mkdocs-material=="9.*" # (1)!
    ```

    1.  Material for MkDocs uses [semantic versioning][^2], which is why it's a
        good idea to limit upgrades to the current major version.

        This will make sure that you don't accidentally [upgrade to the next
        major version], which may include breaking changes that silently corrupt
        your site. Additionally, you can use `pip freeze` to create a lockfile,
        so builds are reproducible at all times:

        ```
        pip freeze > requirements.txt
        ```

        Now, the lockfile can be used for installation:

        ```
        pip install -r requirements.txt
        ```

  [^2]:
    Note that improvements of existing features are sometimes released as
    patch releases, like for example improved rendering of content tabs, as
    they're not considered to be new features.

This will automatically install compatible versions of all dependencies:
[MkDocs], [Markdown], [Pygments] and [Python Markdown Extensions]. Material for
MkDocs always strives to support the latest versions, so there's no need to
install those packages separately.

---

:fontawesome-brands-youtube:{ style="color: #EE0F0F" }
__[How to set up Material for MkDocs]__ by @james-willett – :octicons-clock-24:
27m – Learn how to create and host a documentation site using Material for
MkDocs on GitHub Pages in a step-by-step guide.

  [How to set up Material for MkDocs]: https://www.youtube.com/watch?v=xlABhbnNrfI

---

!!! tip

    If you don't have prior experience with Python, we recommend reading
    [Using Python's pip to Manage Your Projects' Dependencies], which is a
    really good introduction on the mechanics of Python package management and
    helps you troubleshoot if you run into errors.

  [Python package]: https://pypi.org/project/mkdocs-material/
  [virtual environment]: https://realpython.com/what-is-pip/#using-pip-in-a-python-virtual-environment
  [semantic versioning]: https://semver.org/
  [upgrade to the next major version]: upgrade.md
  [Markdown]: https://python-markdown.github.io/
  [Pygments]: https://pygments.org/
  [Python Markdown Extensions]: https://facelessuser.github.io/pymdown-extensions/
  [Using Python's pip to Manage Your Projects' Dependencies]: https://realpython.com/what-is-pip/

### with docker

The official [Docker image] is a great way to get up and running in a few
minutes, as it comes with all dependencies pre-installed. Open up a terminal
and pull the image with:

=== "Latest"

    ```
    docker pull squidfunk/mkdocs-material
    ```

=== "9.x"

    ```
    docker pull squidfunk/mkdocs-material:9
    ```

The `mkdocs` executable is provided as an entry point and `serve` is the
default command. If you're not familiar with Docker don't worry, we have you
covered in the following sections.

The following plugins are bundled with the Docker image:

- [mkdocs-minify-plugin]
- [mkdocs-redirects]

  [Docker image]: https://hub.docker.com/r/squidfunk/mkdocs-material/
  [mkdocs-minify-plugin]: https://github.com/byrnereese/mkdocs-minify-plugin
  [mkdocs-redirects]: https://github.com/datarobot/mkdocs-redirects

???+ warning

    The Docker container is intended for local previewing purposes only and
    is not suitable for deployment. This is because the web server used by
    MkDocs for live previews is not designed for production use and may have
    security vulnerabilities.

??? question "How to add plugins to the Docker image?"

    Material for MkDocs only bundles selected plugins in order to keep the size
    of the official image small. If the plugin you want to use is not included,
    you can add them easily. Create a `Dockerfile` and extend the official image:

    ``` Dockerfile title="Dockerfile"
    FROM squidfunk/mkdocs-material
    RUN pip install mkdocs-macros-plugin
    RUN pip install mkdocs-glightbox
    ```

    Next, build the image with the following command:

    ```
    docker build -t squidfunk/mkdocs-material .
    ```

    The new image will have additional packages installed and can be used
    exactly like the official image.

### with git

Material for MkDocs can be directly used from [GitHub] by cloning the
repository into a subfolder of your project root which might be useful if you
want to use the very latest version:

```
git clone https://github.com/squidfunk/mkdocs-material.git
```

Next, install the theme and its dependencies with:

```
pip install -e mkdocs-material
```

  [GitHub]: https://github.com/squidfunk/mkdocs-material
````

## File: docs/index.md
````markdown
---
template: home.html
title: Material for MkDocs
social:
  cards_layout_options:
    title: Documentation that simply works
---

Welcome to Material for MkDocs.
````

## File: docs/license.md
````markdown
# License

**MIT License**

Copyright (c) 2016-2025 Martin Donath

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
IN THE SOFTWARE.
````

## File: docs/philosophy.md
````markdown
# Philosophy

Before settling for Material for MkDocs, it's a good idea to understand the
philosophy behind the project, in order to make sure it aligns with your goals.
This page explains the design principles anchored in Material for MkDocs, and
discusses the [conventions] used in this documentation.

  [conventions]: conventions.md

## Design principles

- **It's just Markdown**: Focus on the content of your documentation and create a professional static site in minutes. No need to know HTML, CSS or JavaScript – let Material for MkDocs do the heavy lifting for you.

- **Works on all devices**: Serve your documentation with confidence – Material for MkDocs automatically adapts to perfectly fit the available screen estate, no matter the type or size of the viewing device. Desktop. Tablet. Mobile. All great.

- **Made to measure**: Make it yours – change the colors, fonts, language, icons, logo, and more with a few lines of configuration. Material for MkDocs can be easily extended and provides many options to alter appearance and behavior.

- **Fast and lightweight**: Don't let your users wait – get incredible value with a small footprint by using one of the fastest themes available with excellent performance, yielding optimal search engine rankings and happy users that return.

- **Maintain ownership**: Make accessibility a priority – users can navigate your
  documentation with touch devices, keyboard, and screen readers. Semantic
  markup ensures that your documentation works for everyone.

- **Open Source**: You're in good company – choose a mature and actively maintained solution built with state-of-the-art Open Source technologies, trusted by more than 50.000 individuals and organizations. Licensed under MIT.
````

## File: docs/publishing-your-site.md
````markdown
# Publishing your site

The great thing about hosting project documentation in a `git` repository is
the ability to deploy it automatically when new changes are pushed. MkDocs
makes this ridiculously simple.

## GitHub Pages

If you're already hosting your code on GitHub, [GitHub Pages] is certainly
the most convenient way to publish your project documentation. It's free of
charge and pretty easy to set up.

  [GitHub Pages]: https://pages.github.com/

### with GitHub Actions

Using [GitHub Actions] you can automate the deployment of your project
documentation. At the root of your repository, create a new GitHub Actions
workflow, e.g. `.github/workflows/ci.yml`, and copy and paste the following
contents:

``` yaml
name: ci # (1)!
on:
  push:
    branches:
      - master # (2)!
      - main
permissions:
  contents: write
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure Git Credentials
        run: |
          git config user.name github-actions[bot]
          git config user.email 41898282+github-actions[bot]@users.noreply.github.com
      - uses: actions/setup-python@v5
        with:
          python-version: 3.x
      - run: echo "cache_id=$(date --utc '+%V')" >> $GITHUB_ENV # (3)!
      - uses: actions/cache@v4
        with:
          key: mkdocs-material-${{ env.cache_id }}
          path: ~/.cache # (4)!
          restore-keys: |
            mkdocs-material-
      - run: pip install mkdocs-material # (5)!
      - run: mkdocs gh-deploy --force
```

1.  You can change the name to your liking.

2.  At some point, GitHub renamed `master` to `main`. If your default branch
    is named `master`, you can safely remove `main`, vice versa.

3.  Store the `cache_id` environmental variable to access it later during cache
    `key` creation. The name is case-sensitive, so be sure to align it with `${{ env.cache_id }}`.

    - The `--utc` option makes sure that each workflow runner uses the same time zone.
    - The `%V` format assures a cache update once a week.
    - You can change the format to `%F` to have daily cache updates.

    You can read the [manual page] to learn more about the formatting options of the `date` command.

4.  Some Material for MkDocs plugins use [caching] to speed up repeated
    builds, and store the results in the `~/.cache` directory.

5.  This is the place to install further [MkDocs plugins] or Markdown
    extensions with `pip` to be used during the build:

    ``` sh
    pip install \
      mkdocs-material \
      mkdocs-awesome-pages-plugin \
      ...
    ```

Now, when a new commit is pushed to either the `master` or `main` branches,
the static site is automatically built and deployed. Push your changes to see
the workflow in action.

If the GitHub Page doesn't show up after a few minutes, go to the settings of
your repository and ensure that the [publishing source branch] for your GitHub
Page is set to `gh-pages`.

Your documentation should shortly appear at `<username>.github.io/<repository>`.

To publish your site on a custom domain, please refer to the [MkDocs documentation].

  [GitHub Actions]: https://github.com/features/actions
  [MkDocs plugins]: https://github.com/mkdocs/mkdocs/wiki/MkDocs-Plugins
  [personal access token]: https://docs.github.com/en/github/authenticating-to-github/creating-a-personal-access-token
  [built-in optimize plugin]: plugins/optimize.md
  [GitHub secrets]: https://docs.github.com/en/actions/configuring-and-managing-workflows/creating-and-storing-encrypted-secrets
  [publishing source branch]: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
  [manual page]: https://man7.org/linux/man-pages/man1/date.1.html
  [caching]: plugins/requirements/caching.md
  [MkDocs documentation]: https://www.mkdocs.org/user-guide/deploying-your-docs/#custom-domains

### with MkDocs

If you prefer to deploy your project documentation manually, you can just invoke
the following command from the directory containing the `mkdocs.yml` file:

```
mkdocs gh-deploy --force
```

This will build your documentation and deploy it to a branch
`gh-pages` in your repository. See [this overview in the MkDocs
documentation] for more information. For a description of the
arguments, see [the documentation for the command].

  [this overview in the MkDocs documentation]: https://www.mkdocs.org/user-guide/deploying-your-docs/#project-pages
  [the documentation for the command]: https://www.mkdocs.org/user-guide/cli/#mkdocs-gh-deploy

## GitLab Pages

If you're hosting your code on GitLab, deploying to [GitLab Pages] can be done
by using the [GitLab CI] task runner. At the root of your repository, create a
task definition named `.gitlab-ci.yml` and copy and paste the following
contents:

``` yaml
pages:
  stage: deploy
  image: python:latest
  script:
    - pip install mkdocs-material
    - mkdocs build --site-dir public
  cache:
    key: ${CI_COMMIT_REF_SLUG}
    paths:
      - ~/.cache/ # (1)!
  artifacts:
    paths:
      - public
  rules:
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
```

1.  Some Material for MkDocs plugins use [caching] to speed up repeated
    builds, and store the results in the `~/.cache` directory.

Now, when a new commit is pushed to the [default branch] (typically `master` or
`main`), the static site is automatically built and deployed. Commit and push
the file to your repository to see the workflow in action.

Your documentation is not published under `<username>.gitlab.io/<repository>`
by default since **GitLab 17.4** [^1]. However, if you prefer a cleaner URL
structure, such as `<username>.gitlab.io/<repository>`, you need to adjust
your configuration.

To switch from a unique domain to the traditional URL structure, follow
these steps:

1.  Locate Your Repository
2.  Go to **Settings › Pages** in the repository menu.
3.  In the **Unique domain settings** section, **uncheck** the box labeled
4.  **Use unique domain**.
5.  Click **Save changes** to apply the update.

Now you can reach your documentation under `<username>.gitlab.io/<repository>`.

[^1]: [Release notes for Gitlab 17.4](https://about.gitlab.com/releases/2024/09/19/gitlab-17-4-released/)

## Other

Since we can't cover all possible platforms, we rely on community contributed
guides that explain how to deploy websites built with Material for MkDocs to
other providers:

<div class="mdx-columns" markdown>

- [:simple-cloudflarepages: Cloudflare Pages][Cloudflare Pages]
- [:material-airballoon-outline: Fly.io][Flyio]
- [:simple-netlify: Netlify][Netlify]
- [:simple-scaleway: Scaleway][Scaleway]

</div>

  [GitLab Pages]: https://gitlab.com/pages
  [GitLab CI]: https://docs.gitlab.com/ee/ci/
  [masked custom variables]: https://docs.gitlab.com/ee/ci/variables/#mask-a-cicd-variable
  [default branch]: https://docs.gitlab.com/ee/user/project/repository/branches/default.html
  [Cloudflare Pages]: https://deborahwrites.com/guides/deploy-host-mkdocs/deploy-mkdocs-material-cloudflare/
  [Flyio]: https://documentation.breadnet.co.uk/cloud/fly/mkdocs-on-fly/
  [Netlify]: https://deborahwrites.com/guides/deploy-host-mkdocs/deploy-mkdocs-material-netlify/
  [Scaleway]: https://www.scaleway.com/en/docs/tutorials/using-bucket-website-with-mkdocs/
````

## File: docs/schema.json
````json
{
  "$schema": "https://json-schema.org/draft-07/schema",
  "title": "Material for MkDocs",
  "markdownDescription": "Configuration",
  "type": "object",
  "properties": {
    "INHERIT": {
      "title": "Inherit from configuration",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#configuration-inheritance",
      "pattern": "\\.yml$"
    },
    "site_name": {
      "title": "Site name, used in header, title and drawer",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#site_name",
      "type": "string"
    },
    "site_url": {
      "title": "Site URL",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#site_url",
      "type": "string"
    },
    "site_author": {
      "title": "Site author, used in document head",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#site_author",
      "type": "string"
    },
    "site_description": {
      "title": "Site description, used in document head and in social cards",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#site_description",
      "type": "string"
    },
    "repo_name": {
      "title": "Repository name, used in header",
      "markdownDescription": "https://squidfunk.github.io/mkdocs-material/setup/adding-a-git-repository/#repository-name",
      "type": "string"
    },
    "repo_url": {
      "title": "Repository URL",
      "markdownDescription": "https://squidfunk.github.io/mkdocs-material/setup/adding-a-git-repository/#repository",
      "type": "string"
    },
    "edit_uri": {
      "title": "Path from repository root to directory containing Markdown",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#edit_uri",
      "type": "string"
    },
    "edit_uri_template": {
      "title": "More flexible variant of edit_uri",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#edit_uri_template",
      "type": "string"
    },
    "copyright": {
      "title": "Copyright, used in footer",
      "markdownDescription": "https://squidfunk.github.io/mkdocs-material/setup/setting-up-the-footer/#copyright-notice",
      "type": "string"
    },
    "docs_dir": {
      "title": "Directory containing the Markdown sources",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#docs_dir",
      "type": "string",
      "default": "docs"
    },
    "site_dir": {
      "title": "Directory containing the HTML output",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#site_dir",
      "type": "string",
      "default": "site"
    },
    "use_directory_urls": {
      "title": "Pages are located in their own directories",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#use_directory_urls",
      "type": "boolean",
      "default": false
    },
    "extra_templates": {
      "title": "Additional HTML files to include",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#extra_templates",
      "type": "array",
      "items": {
        "title": "Path to HTML file",
        "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#extra_templates",
        "pattern": "\\.html$"
      },
      "uniqueItems": true,
      "minItems": 1
    },
    "extra_css": {
      "title": "Additional CSS files to include",
      "markdownDescription": "https://squidfunk.github.io/mkdocs-material/customization/#additional-css",
      "type": "array",
      "items": {
        "title": "Path to CSS file",
        "markdownDescription": "https://squidfunk.github.io/mkdocs-material/customization/#additional-css",
        "pattern": "\\.css($|\\?)"
      },
      "uniqueItems": true,
      "minItems": 1
    },
    "extra_javascript": {
      "title": "Additional JavaScript files to include",
      "markdownDescription": "https://squidfunk.github.io/mkdocs-material/customization/#additional-javascript",
      "type": "array",
      "items": {
        "title": "Path to JavaScript file (may be local or absolute URL to external JS)",
        "markdownDescription": "https://squidfunk.github.io/mkdocs-material/customization/#additional-javascript"
      },
      "uniqueItems": true,
      "minItems": 1
    },
    "hooks": {
      "title": "Hooks",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#hooks",
      "type": "array",
      "items": {
        "title": "Path to Python file",
        "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#hooks",
        "pattern": "\\.py$"
      },
      "uniqueItems": true,
      "minItems": 1
    },
    "strict": {
      "title": "Strict mode",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#strict",
      "type": "boolean",
      "default": false
    },
    "dev_addr": {
      "title": "Development IP Address",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#dev_addr",
      "type": "string",
      "default": "127.0.0.1:8000"
    },
    "remote_branch": {
      "title": "Remote branch to deploy to",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#remote_branch",
      "type": "string",
      "default": "gh-pages"
    },
    "remote_name": {
      "title": "Remote origin to deploy to",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#remote_name",
      "type": "string",
      "default": "origin"
    },
    "theme": {
      "$ref": "schema/theme.json"
    },
    "plugins": {
      "$ref": "schema/plugins.json"
    },
    "markdown_extensions": {
      "$ref": "schema/extensions.json"
    },
    "extra": {
      "$ref": "schema/extra.json"
    },
    "nav": {
      "$ref": "schema/nav.json"
    },
    "validation": {
      "$ref": "schema/validation.json"
    },
    "exclude_docs": {
      "title": "Pattern to declare files to exclude from build",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#exclude_docs",
      "type": "string"
    },
    "draft_docs": {
      "title": "Pattern to declare draft documents",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#draft_docs",
      "type": "string"
    },
    "not_in_nav": {
      "title": "Pattern to declare pages that do not appear in the navigation",
      "markdownDescription": "https://www.mkdocs.org/user-guide/configuration/#not_in_nav",
      "type": "string"
    },
    "watch": {
      "items": {
        "title": "Path to watch for changes",
        "type": "string"
      },
      "type": "array"
    }
  },
  "additionalProperties": false
}
````

## File: docs/upgrade.md
````markdown
# How to upgrade

Upgrade to the latest version with:

```
pip install --upgrade --force-reinstall mkdocs-material
```

Show the currently installed version with:

```
pip show mkdocs-material
```

## Upgrading from 8.x to 9.x

This major release includes a brand new search implementation that is faster
and allows for rich previews, advanced tokenization and better highlighting.
It was available as part of Insiders for over a year, and now that the funding
goal was hit, makes its way into the community edition.

### Changes to `mkdocs.yml`

#### `content.code.copy`

The copy-to-clipboard buttons are now opt-in and can be enabled or disabled
per block. If you wish to enable them for all code blocks, add the following
lines to `mkdocs.yml`:

``` yaml
theme:
  features:
    - content.code.copy
```

#### `content.action.*`

A "view source" button can be shown next to the "edit this page" button, both
of which must now be explicitly enabled. Add the following lines to
`mkdocs.yml`:

``` yaml
theme:
  features:
    - content.action.edit
    - content.action.view
```

#### `navigation.footer`

The _previous_ and _next_ buttons in the footer are now opt-in. If you wish to
keep them for your documentation, add the following lines to `mkdocs.yml`:

``` yaml
theme:
  features:
    - navigation.footer
```

#### `theme.language`

The Korean and Norwegian language codes were renamed, as they were non-standard:

- `kr` to `ko`
- `no` to `nb`

#### `feedback.ratings`

The old, nameless placeholders were removed (after being deprecated for several
months). Make sure to switch to the new named placeholders `{title}` and `{url}`:

```
https://github.com/.../issues/new/?title=[Feedback]+{title}+-+{url}
```

### Changes to `*.html` files

The templates have undergone a series of changes. If you have customized
Material for MkDocs with theme extension, be sure to incorporate the latest
changes into your templates. A good starting point is to [inspect the diff].

!!! warning "Built-in plugins not working after upgrade?"

    If one of the built-in plugins (search or tags) doesn't work anymore without
    any apparent error or cause, it is very likely related to custom overrides.
    [MkDocs 1.4.1] and above allow themes to namespace built-in plugins, which
    Material for MkDocs 9 now does in order to allow authors to use third-party
    plugins with the same name as built-in plugins. Search your overrides for
    [`"in config.plugins"`][in config.plugins] and add the `material/` namespace.
    Affected partials:

    - [`content.html`][content.html]
    - [`header.html`][header.html]

  [inspect the diff]: https://github.com/squidfunk/mkdocs-material/pull/4628/files#diff-3ca112736b9164701b599f34780107abf14bb79fe110c478cac410be90899828
  [MkDocs 1.4.1]: https://github.com/mkdocs/mkdocs/releases/tag/1.4.1
  [in config.plugins]: https://github.com/squidfunk/mkdocs-material/search?q=%22in+config.plugins%22
  [content.html]: https://github.com/squidfunk/mkdocs-material/blob/master/src/templates/partials/content.html
  [header.html]: https://github.com/squidfunk/mkdocs-material/blob/master/src/templates/partials/header.html

## Upgrading from 7.x to 8.x

### What's new?

- Added support for code annotations
- Added support for anchor tracking
- Added support for version warning
- Added `copyright` partial for easier override
- Removed deprecated content tabs legacy implementation
- Removed deprecated `seealso` admonition type
- Removed deprecated `site_keywords` setting (unsupported by MkDocs)
- Removed deprecated prebuilt search index support
- Removed deprecated web app manifest – use customization
- Removed `extracopyright` variable – use new `copyright` partial
- Removed Disqus integration – use customization
- Switched to `:is()` selectors for simple selector lists
- Switched autoprefixer from `last 4 years` to `last 2 years`
- Improved CSS overall to match modern standards
- Improved CSS variable semantics for fonts
- Improved extensibility by restructuring partials
- Improved handling of `details` when printing
- Improved keyboard navigation for footnotes
- Fixed #3214: Search highlighting breaks site when empty

### Changes to `mkdocs.yml`

#### `pymdownx.tabbed`

Support for the legacy style of the [Tabbed] extension was dropped in favor
of the new, alternate implementation which has [better behavior on mobile
viewports]:

=== "8.x"

    ``` yaml
    markdown_extensions:
      - pymdownx.tabbed:
          alternate_style: true
    ```

=== "7.x"

    ``` yaml
    markdown_extensions:
      - pymdownx.tabbed
    ```

  [Tabbed]: setup/extensions/python-markdown-extensions.md#tabbed
  [better behavior on mobile viewports]: https://x.com/squidfunk/status/1424740370596958214

#### `pymdownx.superfences`

The `*-experimental` suffix must be removed from the [custom fence][SuperFences]
class property, which is used to target code blocks to be rendered as [diagrams]
using [Mermaid.js]:

=== "8.x"

    ``` yaml
    markdown_extensions:
      - pymdownx.superfences:
          custom_fences:
            - name: mermaid
              class: mermaid
              format: !!python/name:pymdownx.superfences.fence_code_format
    ```

=== "7.x"

    ``` yaml
    markdown_extensions:
      - pymdownx.superfences:
          custom_fences:
            - name: mermaid
              class: mermaid-experimental
              format: !!python/name:pymdownx.superfences.fence_code_format
    ```

  [SuperFences]: setup/extensions/python-markdown-extensions.md#superfences
  [diagrams]: reference/diagrams.md
  [Mermaid.js]: https://mermaid-js.github.io/mermaid/

#### `google_analytics`

This option was [deprecated in MkDocs 1.2.0], as the implementation of a
JavaScript-based analytics integration is the responsibility of a theme.
The following lines must be changed:

=== "8.x"

    ``` yaml
    extra:
      analytics:
        provider: google
        property: UA-XXXXXXXX-X
    ```

=== "7.x"

    ``` yaml
    google_analytics:
      - UA-XXXXXXXX-X
      - auto
    ```

  [deprecated in MkDocs 1.2.0]: https://www.mkdocs.org/about/release-notes/#backward-incompatible-changes-in-12

### Changes to `*.html` files { data-search-exclude }

The templates have undergone a set of changes to make them future-proof. If
you've used theme extension to override a block or template, make sure that it
matches the new structure:

- If you've overridden a __block__, check `base.html` for potential changes
- If you've overridden a __template__, check the respective `*.html` file for
  potential changes

=== ":octicons-file-code-16: `base.html`"

    ``` diff
    @@ -13,11 +13,6 @@
           {% elif config.site_description %}
             <meta name="description" content="{{ config.site_description }}">
           {% endif %}
    -      {% if page and page.meta and page.meta.keywords %}
    -        <meta name="keywords" content="{{ page.meta.keywords }}">
    -      {% elif config.site_keywords %}
    -        <meta name="keywords" content="{{ config.site_keywords }}">
    -      {% endif %}
           {% if page and page.meta and page.meta.author %}
             <meta name="author" content="{{ page.meta.author }}">
           {% elif config.site_author %}
    @@ -61,15 +56,13 @@
                 font.text | replace(' ', '+') + ':300,400,400i,700%7C' +
                 font.code | replace(' ', '+')
               }}&display=fallback">
    -        <style>:root{--md-text-font-family:"{{ font.text }}";--md-code-font-family:"{{ font.code }}"}</style>
    +        <style>:root{--md-text-font:"{{ font.text }}";--md-code-font:"{{ font.code }}"}</style>
           {% endif %}
         {% endblock %}
    -    {% if config.extra.manifest %}
    -      <link rel="manifest" href="{{ config.extra.manifest | url }}" crossorigin="use-credentials">
    -    {% endif %}
         {% for path in config["extra_css"] %}
           <link rel="stylesheet" href="{{ path | url }}">
         {% endfor %}
    +    {% include "partials/javascripts/base.html" %}
         {% block analytics %}
           {% include "partials/integrations/analytics.html" %}
         {% endblock %}
    @@ -89,7 +82,6 @@
         <body dir="{{ direction }}">
       {% endif %}
         {% set features = config.theme.features or [] %}
    -    {% include "partials/javascripts/base.html" %}
         {% if not config.theme.palette is mapping %}
           {% include "partials/javascripts/palette.html" %}
         {% endif %}
    @@ -106,13 +98,25 @@
         </div>
         <div data-md-component="announce">
           {% if self.announce() %}
    -        <aside class="md-banner md-announce">
    -          <div class="md-banner__inner md-announce__inner md-grid md-typeset">
    +        <aside class="md-banner">
    +          <div class="md-banner__inner md-grid md-typeset">
                 {% block announce %}{% endblock %}
               </div>
             </aside>
           {% endif %}
         </div>
    +    {% if config.extra.version %}
    +      <div data-md-component="outdated" hidden>
    +        <aside class="md-banner md-banner--warning">
    +          {% if self.outdated() %}
    +            <div class="md-banner__inner md-grid md-typeset">
    +              {% block outdated %}{% endblock %}
    +            </div>
    +            {% include "partials/javascripts/outdated.html" %}
    +          {% endif %}
    +        </aside>
    +      </div>
    +    {% endif %}
         {% block header %}
           {% include "partials/header.html" %}
         {% endblock %}
    @@ -156,25 +160,7 @@
               <div class="md-content" data-md-component="content">
                 <article class="md-content__inner md-typeset">
                   {% block content %}
    -                {% if page.edit_url %}
    -                  <a href="{{ page.edit_url }}" title="{{ lang.t('edit.link.title') }}" class="md-content__button md-icon">
    -                    {% include ".icons/material/pencil.svg" %}
    -                  </a>
    -                {% endif %}
    -                {% if not "\x3ch1" in page.content %}
    -                  <h1>{{ page.title | d(config.site_name, true)}}</h1>
    -                {% endif %}
    -                {{ page.content }}
    -                {% if page and page.meta %}
    -                  {% if page.meta.git_revision_date_localized or
    -                        page.meta.revision_date
    -                  %}
    -                    {% include "partials/source-file.html" %}
    -                  {% endif %}
    -                {% endif %}
    -              {% endblock %}
    -              {% block disqus %}
    -                {% include "partials/integrations/disqus.html" %}
    +                {% include "partials/content.html" %}
                   {% endblock %}
                 </article>
               </div>
    ```

    ``` diff
    @@ -38,13 +38,6 @@
             <meta name="description" content="{{ config.site_description }}" />
           {% endif %}

    -      <!-- Page keywords -->
    -      {% if page and page.meta and page.meta.keywords %}
    -        <meta name="keywords" content="{{ page.meta.keywords }}" />
    -      {% elif config.site_keywords %}
    -        <meta name="keywords" content="{{ config.site_keywords }}" />
    -      {% endif %}
    -
           <!-- Page author -->
           {% if page and page.meta and page.meta.author %}
             <meta name="author" content="{{ page.meta.author }}" />
    @@ -120,27 +113,21 @@
             />
             <style>
               :root {
    -            --md-text-font-family: "{{ font.text }}";
    -            --md-code-font-family: "{{ font.code }}";
    +            --md-text-font: "{{ font.text }}";
    +            --md-code-font: "{{ font.code }}";
               }
             </style>
           {% endif %}
         {% endblock %}

    -    <!-- Progressive Web App Manifest -->
    -    {% if config.extra.manifest %}
    -      <link
    -        rel="manifest"
    -        href="{{ config.extra.manifest | url }}"
    -        crossorigin="use-credentials"
    -      />
    -    {% endif %}
    -
         <!-- Custom style sheets -->
         {% for path in config["extra_css"] %}
           <link rel="stylesheet" href="{{ path | url }}" />
         {% endfor %}

    +    <!-- Helper functions for inline scripts -->
    +    {% include "partials/javascripts/base.html" %}
    +
         <!-- Analytics -->
         {% block analytics %}
           {% include "partials/integrations/analytics.html" %}
    @@ -172,7 +159,6 @@

         <!-- Retrieve features from configuration -->
         {% set features = config.theme.features or [] %}
    -    {% include "partials/javascripts/base.html" %}

         <!-- User preference: color palette -->
         {% if not config.theme.palette is mapping %}
    @@ -214,14 +200,28 @@
         <!-- Announcement bar -->
         <div data-md-component="announce">
           {% if self.announce() %}
    -        <aside class="md-banner md-announce">
    -          <div class="md-banner__inner md-announce__inner md-grid md-typeset">
    +        <aside class="md-banner">
    +          <div class="md-banner__inner md-grid md-typeset">
                 {% block announce %}{% endblock %}
               </div>
             </aside>
           {% endif %}
         </div>

    +    <!-- Version warning -->
    +    {% if config.extra.version %}
    +      <div data-md-component="outdated" hidden>
    +        <aside class="md-banner md-banner--warning">
    +          {% if self.outdated() %}
    +            <div class="md-banner__inner md-grid md-typeset">
    +              {% block outdated %}{% endblock %}
    +            </div>
    +            {% include "partials/javascripts/outdated.html" %}
    +          {% endif %}
    +        </aside>
    +      </div>
    +    {% endif %}
    +
         <!-- Header -->
         {% block header %}
           {% include "partials/header.html" %}
    @@ -295,49 +295,11 @@
                   {% block content %}
    -
    -                <!-- Edit button -->
    -                {% if page.edit_url %}
    -                  <a
    -                    href="{{ page.edit_url }}"
    -                    title="{{ lang.t('edit.link.title') }}"
    -                    class="md-content__button md-icon"
    -                  >
    -                    {% include ".icons/material/pencil.svg" %}
    -                  </a>
    -                {% endif %}
    -
    -                <!--
    -                  Hack: check whether the content contains a h1 headline. If it
    -                  doesn't, the page title (or respectively site name) is used
    -                  as the main headline.
    -                -->
    -                {% if not "\x3ch1" in page.content %}
    -                  <h1>{{ page.title | d(config.site_name, true)}}</h1>
    -                {% endif %}
    -
    -                <!-- Markdown content -->
    -                {{ page.content }}
    -
    -                <!-- Last update of source file -->
    -                {% if page and page.meta %}
    -                  {% if page.meta.git_revision_date_localized or
    -                        page.meta.revision_date
    -                  %}
    -                    {% include "partials/source-file.html" %}
    -                  {% endif %}
    -                {% endif %}
    -              {% endblock %}
    -
    -              <!-- Disqus integration -->
    -              {% block disqus %}
    -                {% include "partials/integrations/disqus.html" %}
    +                {% include "partials/content.html" %}
                   {% endblock %}
                 </article>
               </div>
    ```

=== ":octicons-file-code-16: `partials/copyright.html`"

    ``` diff
    @@ -0,0 +1,16 @@
    +{#-
    +  This file was automatically generated - do not edit
    +-#}
    +<div class="md-copyright">
    +  {% if config.copyright %}
    +    <div class="md-copyright__highlight">
    +      {{ config.copyright }}
    +    </div>
    +  {% endif %}
    +  {% if not config.extra.generator == false %}
    +    Made with
    +    <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
    +      Material for MkDocs
    +    </a>
    +  {% endif %}
    +</div>
    ```

=== ":octicons-file-code-16: `partials/footer.html`"

    ``` diff
    @@ -41,21 +40,10 @@
       {% endif %}
       <div class="md-footer-meta md-typeset">
         <div class="md-footer-meta__inner md-grid">
    -      <div class="md-footer-copyright">
    -        {% if config.copyright %}
    -          <div class="md-footer-copyright__highlight">
    -            {{ config.copyright }}
    -          </div>
    -        {% endif %}
    -        {% if not config.extra.generator == false %}
    -          Made with
    -          <a href="https://squidfunk.github.io/mkdocs-material/" target="_blank" rel="noopener">
    -            Material for MkDocs
    -          </a>
    -        {% endif %}
    -        {{ extracopyright }}
    -      </div>
    -      {% include "partials/social.html" %}
    +      {% include "partials/copyright.html" %}
    +      {% if config.extra.social %}
    +        {% include "partials/social.html" %}
    +      {% endif %}
         </div>
       </div>
     </footer>
    ```

=== ":octicons-file-code-16: `partials/social.html`"

    ``` diff
    @@ -4,17 +4,15 @@
    -{% if config.extra.social %}
    -  <div class="md-footer-social">
    -    {% for social in config.extra.social %}
    -      {% set title = social.name %}
    -      {% if not title and "//" in social.link %}
    -        {% set _,url = social.link.split("//") %}
    -        {% set title = url.split("/")[0] %}
    -      {% endif %}
    -      <a href="{{ social.link }}" target="_blank" rel="noopener" title="{{ title | e }}" class="md-footer-social__link">
    -        {% include ".icons/" ~ social.icon ~ ".svg" %}
    -      </a>
    -    {% endfor %}
    -  </div>
    -{% endif %}
    +<div class="md-social">
    +  {% for social in config.extra.social %}
    +    {% set title = social.name %}
    +    {% if not title and "//" in social.link %}
    +      {% set _, url = social.link.split("//") %}
    +      {% set title  = url.split("/")[0] %}
    +    {% endif %}
    +    <a href="{{ social.link }}" target="_blank" rel="noopener" title="{{ title | e }}" class="md-social__link">
    +      {% include ".icons/" ~ social.icon ~ ".svg" %}
    +    </a>
    +  {% endfor %}
    +</div>
    ```

## Upgrading from 6.x to 7.x

### What's new?

- Added support for deploying multiple versions
- Added support for integrating a language selector
- Added support for rendering admonitions as inline blocks
- Rewrite of the underlying reactive architecture
- Removed Webpack in favor of reactive build strategy (–480 dependencies)
- Fixed keyboard navigation for code blocks after content tabs switch

### Changes to `mkdocs.yml`

#### `extra.version.method`

The versioning method configuration was renamed to `extra.version.provider` to
allow for different versioning strategies in the future:

=== "7.x"

    ``` yaml
    extra:
      version:
        provider: mike
    ```

=== "6.x"

    ``` yaml
    extra:
      version:
        method: mike
    ```

### Changes to `*.html` files { data-search-exclude }

The templates have undergone a set of changes to make them future-proof. If
you've used theme extension to override a block or template, make sure that it
matches the new structure:

- If you've overridden a __block__, check `base.html` for potential changes
- If you've overridden a __template__, check the respective `*.html` file for
  potential changes

=== ":octicons-file-code-16: `base.html`"

    ``` diff
    @@ -61,7 +61,7 @@
                 font.text | replace(' ', '+') + ':300,400,400i,700%7C' +
                 font.code | replace(' ', '+')
               }}&display=fallback">
    -        <style>body,input{font-family:"{{ font.text }}",-apple-system,BlinkMacSystemFont,Helvetica,Arial,sans-serif}code,kbd,pre{font-family:"{{ font.code }}",SFMono-Regular,Consolas,Menlo,monospace}</style>
    +        <style>:root{--md-text-font-family:"{{ font.text }}";--md-code-font-family:"{{ font.code }}"}</style>
           {% endif %}
         {% endblock %}
         {% if config.extra.manifest %}
    @@ -131,7 +131,7 @@
                   {% if page and page.meta and page.meta.hide %}
                     {% set hidden = "hidden" if "navigation" in page.meta.hide %}
                   {% endif %}
    -              <div class="md-sidebar md-sidebar--primary" data-md-component="navigation" {{ hidden }}>
    +              <div class="md-sidebar md-sidebar--primary" data-md-component="sidebar" data-md-type="navigation" {{ hidden }}>
                     <div class="md-sidebar__scrollwrap">
                       <div class="md-sidebar__inner">
                         {% include "partials/nav.html" %}
    @@ -143,7 +143,7 @@
                   {% if page and page.meta and page.meta.hide %}
                     {% set hidden = "hidden" if "toc" in page.meta.hide %}
                   {% endif %}
    -              <div class="md-sidebar md-sidebar--secondary" data-md-component="toc" {{ hidden }}>
    +              <div class="md-sidebar md-sidebar--secondary" data-md-component="sidebar" data-md-type="toc" {{ hidden }}>
                     <div class="md-sidebar__scrollwrap">
                       <div class="md-sidebar__inner">
                         {% include "partials/toc.html" %}
    @@ -152,7 +152,7 @@
                   </div>
                 {% endif %}
               {% endblock %}
    -          <div class="md-content">
    +          <div class="md-content" data-md-component="content">
                 <article class="md-content__inner md-typeset">
                   {% block content %}
                     {% if page.edit_url %}
    @@ -183,10 +183,18 @@
             {% include "partials/footer.html" %}
           {% endblock %}
         </div>
    -    {% block scripts %}
    -      <script src="{{ 'assets/javascripts/vendor.18f0862e.min.js' | url }}"></script>
    -      <script src="{{ 'assets/javascripts/bundle.994580cf.min.js' | url }}"></script>
    -      {%- set translations = {} -%}
    +    <div class="md-dialog" data-md-component="dialog">
    +      <div class="md-dialog__inner md-typeset"></div>
    +    </div>
    +    {% block config %}
    +      {%- set app = {
    +        "base": base_url,
    +        "features": features,
    +        "translations": {},
    +        "search": "assets/javascripts/workers/search.217ffd95.min.js" | url,
    +        "version": config.extra.version or None
    +      } -%}
    +      {%- set translations = app.translations -%}
           {%- for key in [
             "clipboard.copy",
             "clipboard.copied",
    @@ -204,19 +212,12 @@
           ] -%}
             {%- set _ = translations.update({ key: lang.t(key) }) -%}
           {%- endfor -%}
    -      <script id="__lang" type="application/json">
    -        {{- translations | tojson -}}
    -      </script>
    -      {% block config %}{% endblock %}
    -      <script>
    -        app = initialize({
    -          base: "{{ base_url }}",
    -          features: {{ features or [] | tojson }},
    -          search: Object.assign({
    -            worker: "{{ 'assets/javascripts/worker/search.9c0e82ba.min.js' | url }}"
    -          }, typeof search !== "undefined" && search)
    -        })
    +      <script id="__config" type="application/json">
    +        {{- app | tojson -}}
           </script>
    +    {% endblock %}
    +    {% block scripts %}
    +      <script src="{{ 'assets/javascripts/bundle.926459b3.min.js' | url }}"></script>
           {% for path in config["extra_javascript"] %}
             <script src="{{ path | url }}"></script>
           {% endfor %}
    ```

=== ":octicons-file-code-16: `partials/footer.html`"

    ``` diff
    -    <div class="md-footer-nav">
    -      <nav class="md-footer-nav__inner md-grid" aria-label="{{ lang.t('footer.title') }}">
    -        {% if page.previous_page %}
    -          <a href="{{ page.previous_page.url | url }}" class="md-footer-nav__link md-footer-nav__link--prev" rel="prev">
    -            <div class="md-footer-nav__button md-icon">
    -              {% include ".icons/material/arrow-left.svg" %}
    -            </div>
    -            <div class="md-footer-nav__title">
    -              <div class="md-ellipsis">
    -                <span class="md-footer-nav__direction">
    -                  {{ lang.t("footer.previous") }}
    -                </span>
    -                {{ page.previous_page.title }}
    -              </div>
    -            </div>
    -          </a>
    -        {% endif %}
    -        {% if page.next_page %}
    -          <a href="{{ page.next_page.url | url }}" class="md-footer-nav__link md-footer-nav__link--next" rel="next">
    -            <div class="md-footer-nav__title">
    -              <div class="md-ellipsis">
    -                <span class="md-footer-nav__direction">
    -                  {{ lang.t("footer.next") }}
    -                </span>
    -                {{ page.next_page.title }}
    -              </div>
    +    <nav class="md-footer__inner md-grid" aria-label="{{ lang.t('footer.title') }}">
    +      {% if page.previous_page %}
    +        <a href="{{ page.previous_page.url | url }}" class="md-footer__link md-footer__link--prev" rel="prev">
    +          <div class="md-footer__button md-icon">
    +            {% include ".icons/material/arrow-left.svg" %}
    +          </div>
    +          <div class="md-footer__title">
    +            <div class="md-ellipsis">
    +              <span class="md-footer__direction">
    +                {{ lang.t("footer.previous") }}
    +              </span>
    +              {{ page.previous_page.title }}
                 </div>
    -            <div class="md-footer-nav__button md-icon">
    -              {% include ".icons/material/arrow-right.svg" %}
    +          </div>
    +        </a>
    +      {% endif %}
    +      {% if page.next_page %}
    +        <a href="{{ page.next_page.url | url }}" class="md-footer__link md-footer__link--next" rel="next">
    +          <div class="md-footer__title">
    +            <div class="md-ellipsis">
    +              <span class="md-footer__direction">
    +                {{ lang.t("footer.next") }}
    +              </span>
    +              {{ page.next_page.title }}
                 </div>
    -          </a>
    -        {% endif %}
    -      </nav>
    -    </div>
    +          </div>
    +          <div class="md-footer__button md-icon">
    +            {% include ".icons/material/arrow-right.svg" %}
    +          </div>
    +        </a>
    +      {% endif %}
    +    </nav>
       {% endif %}
       <div class="md-footer-meta md-typeset">
         <div class="md-footer-meta__inner md-grid">
    ```

=== ":octicons-file-code-16: `partials/header.html`"

    ``` diff
    @@ -6,21 +6,21 @@
       {% set site_url = site_url ~ "/index.html" %}
     {% endif %}
     <header class="md-header" data-md-component="header">
    -  <nav class="md-header-nav md-grid" aria-label="{{ lang.t('header.title') }}">
    -    <a href="{{ site_url }}" title="{{ config.site_name | e }}" class="md-header-nav__button md-logo" aria-label="{{ config.site_name }}">
    +  <nav class="md-header__inner md-grid" aria-label="{{ lang.t('header.title') }}">
    +    <a href="{{ site_url }}" title="{{ config.site_name | e }}" class="md-header__button md-logo" aria-label="{{ config.site_name }}">
           {% include "partials/logo.html" %}
         </a>
    -    <label class="md-header-nav__button md-icon" for="__drawer">
    +    <label class="md-header__button md-icon" for="__drawer">
           {% include ".icons/material/menu" ~ ".svg" %}
         </label>
    -    <div class="md-header-nav__title" data-md-component="header-title">
    -      <div class="md-header-nav__ellipsis">
    -        <div class="md-header-nav__topic">
    +    <div class="md-header__title" data-md-component="header-title">
    +      <div class="md-header__ellipsis">
    +        <div class="md-header__topic">
               <span class="md-ellipsis">
                 {{ config.site_name }}
               </span>
             </div>
    -        <div class="md-header-nav__topic">
    +        <div class="md-header__topic" data-md-component="header-topic">
               <span class="md-ellipsis">
                 {% if page and page.meta and page.meta.title %}
                   {{ page.meta.title }}
    @@ -31,14 +31,35 @@
             </div>
           </div>
         </div>
    +    <div class="md-header__options">
    +      {% if config.extra.alternate %}
    +        <div class="md-select">
    +          {% set icon = config.theme.icon.alternate or "material/translate" %}
    +          <span class="md-header__button md-icon">
    +            {% include ".icons/" ~ icon ~ ".svg" %}
    +          </span>
    +          <div class="md-select__inner">
    +            <ul class="md-select__list">
    +              {% for alt in config.extra.alternate %}
    +                <li class="md-select__item">
    +                  <a href="{{ alt.link | url }}" class="md-select__link">
    +                    {{ alt.name }}
    +                  </a>
    +                </li>
    +                {% endfor %}
    +            </ul>
    +          </div>
    +        </div>
    +      {% endif %}
    +    </div>
         {% if "search" in config["plugins"] %}
    -      <label class="md-header-nav__button md-icon" for="__search">
    +      <label class="md-header__button md-icon" for="__search">
             {% include ".icons/material/magnify.svg" %}
           </label>
           {% include "partials/search.html" %}
         {% endif %}
         {% if config.repo_url %}
    -      <div class="md-header-nav__source">
    +      <div class="md-header__source">
             {% include "partials/source.html" %}
           </div>
         {% endif %}
    ```

=== ":octicons-file-code-16: `partials/source.html`"

    ``` diff
    @@ -4,5 +4,5 @@
     {% import "partials/language.html" as lang with context %}
    -<a href="{{ config.repo_url }}" title="{{ lang.t('source.link.title') }}" class="md-source">
    +<a href="{{ config.repo_url }}" title="{{ lang.t('source.link.title') }}"  class="md-source" data-md-component="source">
       <div class="md-source__icon md-icon">
         {% set icon = config.theme.icon.repo or "fontawesome/brands/git-alt" %}
         {% include ".icons/" ~ icon ~ ".svg" %}
    ```

=== ":octicons-file-code-16: `partials/toc.html`"

    ``` diff
    @@ -12,7 +12,7 @@
           <span class="md-nav__icon md-icon"></span>
           {{ lang.t("toc.title") }}
         </label>
    -    <ul class="md-nav__list" data-md-scrollfix>
    +    <ul class="md-nav__list" data-md-component="toc" data-md-scrollfix>
           {% for toc_item in toc %}
             {% include "partials/toc-item.html" %}
           {% endfor %}
    ```

## Upgrading from 5.x to 6.x

### What's new?

- Improved search result look and feel
- Improved search result stability while typing
- Improved search result grouping (pages + headings)
- Improved search result relevance and scoring
- Added display of missing query terms to search results
- Reduced size of vendor bundle by 25% (84kb → 67kb)
- Reduced size of the Docker image to improve CI build performance
- Removed hero partial in favor of custom implementation
- Removed deprecated front matter features

### Changes to `mkdocs.yml`

Following is a list of changes that need to be made to `mkdocs.yml`. Note that
you only have to adjust the value if you defined it, so if your configuration
does not contain the key, you can skip it.

#### `theme.features`

All feature flags that can be set from `mkdocs.yml`, like [tabs] and
[instant loading], are now prefixed with the name of the component or
function they apply to, e.g. `navigation.*`:

=== "6.x"

    ``` yaml
    theme:
      features:
        - navigation.tabs
        - navigation.instant
    ```

=== "5.x"

    ``` yaml
    theme:
      features:
        - tabs
        - instant
    ```

  [tabs]: setup/setting-up-navigation.md#navigation-tabs
  [instant loading]: setup/setting-up-navigation.md#instant-loading

### Changes to `*.html` files { data-search-exclude }

The templates have undergone a set of changes to make them future-proof. If
you've used theme extension to override a block or template, make sure that it
matches the new structure:

- If you've overridden a __block__, check `base.html` for potential changes
- If you've overridden a __template__, check the respective `*.html` file for
  potential changes

=== ":octicons-file-code-16: `base.html`"

    ``` diff
    @@ -22,13 +22,6 @@

     {% import "partials/language.html" as lang with context %}

    -<!-- Theme options -->
    -{% set palette = config.theme.palette %}
    -{% if not palette is mapping %}
    -  {% set palette = palette | first %}
    -{% endif %}
    -{% set font = config.theme.font %}
    -
     <!doctype html>
     <html lang="{{ lang.t('language') }}" class="no-js">
       <head>
    @@ -45,21 +38,8 @@
             <meta name="description" content="{{ config.site_description }}" />
           {% endif %}

    -      <!-- Redirect -->
    -      {% if page and page.meta and page.meta.redirect %}
    -        <script>
    -          var anchor = window.location.hash.substr(1)
    -          location.href = '{{ page.meta.redirect }}' +
    -            (anchor ? '#' + anchor : '')
    -        </script>
    -
    -        <!-- Fallback in case JavaScript is not available -->
    -        <meta http-equiv="refresh" content="0; url={{ page.meta.redirect }}" />
    -        <meta name="robots" content="noindex" />
    -        <link rel="canonical" href="{{ page.meta.redirect }}" />
    -
           <!-- Canonical -->
    -      {% elif page.canonical_url %}
    +      {% if page.canonical_url %}
             <link rel="canonical" href="{{ page.canonical_url }}" />
           {% endif %}

    @@ -96,20 +76,21 @@
           <link rel="stylesheet" href="{{ 'assets/stylesheets/main.css' | url }}" />

           <!-- Extra color palette -->
    -      {% if palette.scheme or palette.primary or palette.accent %}
    +      {% if config.theme.palette %}
    +        {% set palette = config.theme.palette %}
             <link
               rel="stylesheet"
               href="{{ 'assets/stylesheets/palette.css' | url }}"
             />
    -      {% endif %}

    -      <!-- Theme-color meta tag for Android -->
    -      {% if palette.primary %}
    -        {% import "partials/palette.html" as map %}
    -        {% set primary = map.primary(
    -          palette.primary | replace(" ", "-") | lower
    -        ) %}
    -        <meta name="theme-color" content="{{ primary }}" />
    +        <!-- Theme-color meta tag for Android -->
    +        {% if palette.primary %}
    +          {% import "partials/palette.html" as map %}
    +          {% set primary = map.primary(
    +            palette.primary | replace(" ", "-") | lower
    +          ) %}
    +          <meta name="theme-color" content="{{ primary }}" />
    +        {% endif %}
           {% endif %}
         {% endblock %}

    @@ -120,7 +101,8 @@
         {% block fonts %}

           <!-- Load fonts from Google -->
    -      {% if font != false %}
    +      {% if config.theme.font != false %}
    +        {% set font = config.theme.font %}
             <link href="https://fonts.gstatic.com" rel="preconnect" crossorigin />
             <link
              rel="stylesheet"
    @@ -169,8 +151,12 @@

       <!-- Text direction and color palette, if defined -->
       {% set direction = config.theme.direction or lang.t('direction') %}
    -  {% if palette.scheme or palette.primary or palette.accent %}
    -    {% set scheme  = palette.scheme | lower %}
    +  {% if config.theme.palette %}
    +    {% set palette = config.theme.palette %}
    +    {% if not palette is mapping %}
    +      {% set palette = palette | first %}
    +    {% endif %}
    +    {% set scheme  = palette.scheme  | replace(" ", "-") | lower %}
         {% set primary = palette.primary | replace(" ", "-") | lower %}
         {% set accent  = palette.accent  | replace(" ", "-") | lower %}
         <body
    @@ -179,18 +165,19 @@
           data-md-color-primary="{{ primary }}"
           data-md-color-accent="{{ accent }}"
         >
    +
    +      <!-- Experimental: set color scheme based on preference -->
    +      {% if "preference" == scheme %}
    +        <script>
    +          if (matchMedia("(prefers-color-scheme: dark)").matches)
    +            document.body.setAttribute("data-md-color-scheme", "slate")
    +        </script>
    +      {% endif %}
    +
       {% else %}
         <body dir="{{ direction }}">
       {% endif %}

    -    <!-- Experimental: set color scheme based on preference -->
    -    {% if "preference" == palette.scheme %}
    -      <script>
    -        if (matchMedia("(prefers-color-scheme: dark)").matches)
    -          document.body.setAttribute("data-md-color-scheme", "slate")
    -      </script>
    -    {% endif %}
    -
         <!--
           State toggles - we need to set autocomplete="off" in order to reset the
           drawer on back button invocation in some browsers
    @@ -243,15 +230,11 @@
         <div class="md-container" data-md-component="container">

           <!-- Hero teaser -->
    -      {% block hero %}
    -        {% if page and page.meta and page.meta.hero %}
    -          {% include "partials/hero.html" with context %}
    -        {% endif %}
    -      {% endblock %}
    +      {% block hero %}{% endblock %}

           <!-- Tabs navigation -->
           {% block tabs %}
    -        {% if "tabs" in config.theme.features %}
    +        {% if "navigation.tabs" in config.theme.features %}
               {% include "partials/tabs.html" %}
             {% endif %}
           {% endblock %}
    @@ -310,13 +293,6 @@
                       </a>
                     {% endif %}

    -                <!-- Link to source file -->
    -                {% block source %}
    -                  {% if page and page.meta and page.meta.source %}
    -                    {% include "partials/source-link.html" %}
    -                  {% endif %}
    -                {% endblock %}
    -
                     <!--
                       Hack: check whether the content contains a h1 headline. If it
                       doesn't, the page title (or respectively site name) is used
    @@ -370,7 +346,10 @@
             "search.result.placeholder",
             "search.result.none",
             "search.result.one",
    -        "search.result.other"
    +        "search.result.other",
    +        "search.result.more.one",
    +        "search.result.more.other",
    +        "search.result.term.missing"
           ] -%}
             {%- set _ = translations.update({ key: lang.t(key) }) -%}
           {%- endfor -%}
    ```

=== ":octicons-file-code-16: `partials/hero.html`"

    ``` diff
    @@ -1,12 +0,0 @@
    -{#-
    -  This file was automatically generated - do not edit
    --#}
    -{% set class = "md-hero" %}
    -{% if "tabs" not in config.theme.features %}
    -  {% set class = "md-hero md-hero--expand" %}
    -{% endif %}
    -<div class="{{ class }}" data-md-component="hero">
    -  <div class="md-hero__inner md-grid">
    -    {{ page.meta.hero }}
    -  </div>
    -</div>
    ```

=== ":octicons-file-code-16: `partials/source-link`"

    ``` diff
    @@ -1,14 +0,0 @@
    -{#-
    -  This file was automatically generated - do not edit
    --#}
    -{% import "partials/language.html" as lang with context %}
    -{% set repo = config.repo_url %}
    -{% if repo | last == "/" %}
    -  {% set repo = repo[:-1] %}
    -{% endif %}
    -{% set path = page.meta.path | default("") %}
    -<a href="{{ [repo, path, page.meta.source] | join('/') }}" title="{{ page.meta.source }}" class="md-content__button md-icon">
    -  {{ lang.t("meta.source") }}
    -  {% set icon = config.theme.icon.repo or "fontawesome/brands/git-alt" %}
    -  {% include ".icons/" ~ icon ~ ".svg" %}
    -</a>
    ```

## Upgrading from 4.x to 5.x

### What's new?

- Reactive architecture – try `#!js app.dialog$.next("Hi!")` in the console
- [Instant loading] – make Material behave like a Single Page Application
- Improved CSS customization with [CSS variables] – set your brand's colors
- Improved CSS resilience, e.g. proper sidebar locking for customized headers
- Improved [icon integration] and configuration – now including over 5k icons
- Added possibility to use any icon for logo, repository and social links
- Search UI does not freeze anymore (moved to web worker)
- Search index built only once when using instant loading
- Improved extensible keyboard handling
- Support for [prebuilt search indexes]
- Support for displaying stars and forks for GitLab repositories
- Support for scroll snapping of sidebars and search results
- Reduced HTML and CSS footprint due to deprecation of Internet Explorer support
- Slight facelifting of some UI elements (admonitions, tables, ...)

  [CSS variables]: setup/changing-the-colors.md#custom-colors
  [icon integration]: reference/icons-emojis.md#search
  [prebuilt search indexes]: plugins/search.md

### Changes to `mkdocs.yml`

Following is a list of changes that need to be made to `mkdocs.yml`. Note that
you only have to adjust the value if you defined it, so if your configuration
does not contain the key, you can skip it.

#### `theme.feature`

Optional features like [tabs] and [instant loading] are now implemented as
flags and can be enabled by listing them in `mkdocs.yml` under `theme.features`:

=== "5.x"

    ``` yaml
    theme:
      features:
        - tabs
        - instant
    ```

=== "4.x"

    ``` yaml
    theme:
      feature:
        tabs: true
    ```

#### `theme.logo.icon`

The logo icon configuration was centralized under `theme.icon.logo` and can now
be set to any of the [icons bundled with the theme][icon integration]:

=== "5.x"

    ``` yaml
    theme:
      icon:
        logo: material/cloud
    ```

=== "4.x"

    ``` yaml
    theme:
      logo:
        icon: cloud
    ```

#### `extra.repo_icon`

The repo icon configuration was centralized under `theme.icon.repo` and can now
be set to any of the [icons bundled with the theme][icon integration]:

=== "5.x"

    ``` yaml
    theme:
      icon:
        repo: fontawesome/brands/gitlab
    ```

=== "4.x"

    ``` yaml
    extra:
      repo_icon: gitlab
    ```

#### `extra.search.*`

Search is now configured as part of the [plugin options]. Note that the
search languages must now be listed as an array of strings and the `tokenizer`
was renamed to `separator`:

=== "5.x"

    ``` yaml
    plugins:
      - search:
          separator: '[\s\-\.]+'
          lang:
            - en
            - de
            - ru
    ```

=== "4.x"

    ``` yaml
    extra:
      search:
        language: en, de, ru
        tokenizer: '[\s\-\.]+'
    ```

  [plugin options]: plugins/search.md

#### `extra.social.*`

Social links stayed in the same place, but the `type` key was renamed to `icon`
in order to match the new way of specifying which icon to be used:

=== "5.x"

    ``` yaml
    extra:
      social:
        - icon: fontawesome/brands/github-alt
          link: https://github.com/squidfunk
    ```

=== "4.x"

    ``` yaml
    extra:
      social:
        - type: github
          link: https://github.com/squidfunk
    ```

### Changes to `*.html` files { data-search-exclude }

The templates have undergone a set of changes to make them future-proof. If
you've used theme extension to override a block or template, make sure that it
matches the new structure:

- If you've overridden a __block__, check `base.html` for potential changes
- If you've overridden a __template__, check the respective `*.html` file for
  potential changes

=== ":octicons-file-code-16: `base.html`"

    ``` diff
    @@ -4,7 +4,6 @@
     {% import "partials/language.html" as lang with context %}
    -{% set feature = config.theme.feature %}
     {% set palette = config.theme.palette %}
     {% set font = config.theme.font %}
     <!doctype html>
    @@ -30,19 +29,6 @@
           {% elif config.site_author %}
             <meta name="author" content="{{ config.site_author }}">
           {% endif %}
    -      {% for key in [
    -        "clipboard.copy",
    -        "clipboard.copied",
    -        "search.language",
    -        "search.pipeline.stopwords",
    -        "search.pipeline.trimmer",
    -        "search.result.none",
    -        "search.result.one",
    -        "search.result.other",
    -        "search.tokenizer"
    -      ] %}
    -        <meta name="lang:{{ key }}" content="{{ lang.t(key) }}">
    -      {% endfor %}
           <link rel="shortcut icon" href="{{ config.theme.favicon | url }}">
           <meta name="generator" content="mkdocs-{{ mkdocs_version }}, mkdocs-material-5.0.0">
         {% endblock %}
    @@ -56,9 +42,9 @@
           {% endif %}
         {% endblock %}
         {% block styles %}
    -      <link rel="stylesheet" href="{{ 'assets/stylesheets/application.********.css' | url }}">
    +      <link rel="stylesheet" href="{{ 'assets/stylesheets/main.********.min.css' | url }}">
           {% if palette.primary or palette.accent %}
    -        <link rel="stylesheet" href="{{ 'assets/stylesheets/application-palette.********.css' | url }}">
    +        <link rel="stylesheet" href="{{ 'assets/stylesheets/palette.********.min.css' | url }}">
           {% endif %}
           {% if palette.primary %}
             {% import "partials/palette.html" as map %}
    @@ -69,20 +55,17 @@
           {% endif %}
         {% endblock %}
         {% block libs %}
    -      <script src="{{ 'assets/javascripts/modernizr.********.js' | url }}"></script>
         {% endblock %}
         {% block fonts %}
           {% if font != false %}
             <link href="https://fonts.gstatic.com" rel="preconnect" crossorigin>
             <link rel="stylesheet" href="https://fonts.googleapis.com/css?family={{
                 font.text | replace(' ', '+') + ':300,400,400i,700%7C' +
                 font.code | replace(' ', '+')
               }}&display=fallback">
             <style>body,input{font-family:"{{ font.text }}","Helvetica Neue",Helvetica,Arial,sans-serif}code,kbd,pre{font-family:"{{ font.code }}","Courier New",Courier,monospace}</style>
           {% endif %}
         {% endblock %}
    -    <link rel="stylesheet" href="{{ 'assets/fonts/material-icons.css' | url }}">
         {% if config.extra.manifest %}
           <link rel="manifest" href="{{ config.extra.manifest | url }}" crossorigin="use-credentials">
         {% endif %}
    @@ -95,47 +77,50 @@
         {% endblock %}
         {% block extrahead %}{% endblock %}
       </head>
    +  {% set direction = config.theme.direction | default(lang.t('direction')) %}
       {% if palette.primary or palette.accent %}
         {% set primary = palette.primary | replace(" ", "-") | lower %}
         {% set accent  = palette.accent  | replace(" ", "-") | lower %}
    -    <body dir="{{ lang.t('direction') }}" data-md-color-primary="{{ primary }}" data-md-color-accent="{{ accent }}">
    +    <body dir="{{ direction }}" data-md-color-primary="{{ primary }}" data-md-color-accent="{{ accent }}">
       {% else %}
    -    <body dir="{{ lang.t('direction') }}">
    +    <body dir="{{ direction }}">
       {% endif %}
    -    <svg class="md-svg">
    -      <defs>
    -        {% set platform = config.extra.repo_icon or config.repo_url %}
    -        {% if "github" in platform %}
    -          {% include "assets/images/icons/github.f0b8504a.svg" %}
    -        {% elif "gitlab" in platform %}
    -          {% include "assets/images/icons/gitlab.6dd19c00.svg" %}
    -        {% elif "bitbucket" in platform %}
    -          {% include "assets/images/icons/bitbucket.1b09e088.svg" %}
    -        {% endif %}
    -      </defs>
    -    </svg>
         <input class="md-toggle" data-md-toggle="drawer" type="checkbox" id="__drawer" autocomplete="off">
         <input class="md-toggle" data-md-toggle="search" type="checkbox" id="__search" autocomplete="off">
    -    <label class="md-overlay" data-md-component="overlay" for="__drawer"></label>
    +    <label class="md-overlay" for="__drawer"></label>
    +    <div data-md-component="skip">
    +      {% if page.toc | first is defined %}
    +        {% set skip = page.toc | first %}
    +        <a href="{{ skip.url | url }}" class="md-skip">
    +          {{ lang.t('skip.link.title') }}
    +        </a>
    +      {% endif %}
    +    </div>
    +    <div data-md-component="announce">
    +      {% if self.announce() %}
    +        <aside class="md-announce">
    +          <div class="md-announce__inner md-grid md-typeset">
    +            {% block announce %}{% endblock %}
    +          </div>
    +        </aside>
    +      {% endif %}
    +    </div>
         {% block header %}
           {% include "partials/header.html" %}
         {% endblock %}
    -    <div class="md-container">
    +    <div class="md-container" data-md-component="container">
           {% block hero %}
             {% if page and page.meta and page.meta.hero %}
               {% include "partials/hero.html" with context %}
             {% endif %}
           {% endblock %}
    -      {% if feature.tabs %}
    -        {% include "partials/tabs.html" %}
    -      {% endif %}
    +      {% block tabs %}
    +        {% if "tabs" in config.theme.features %}
    +          {% include "partials/tabs.html" %}
    +        {% endif %}
    +      {% endblock %}
    -      <main class="md-main" role="main">
    -        <div class="md-main__inner md-grid" data-md-component="container">
    +      <main class="md-main" data-md-component="main">
    +        <div class="md-main__inner md-grid">
               {% block site_nav %}
                 {% if nav %}
                   <div class="md-sidebar md-sidebar--primary" data-md-component="navigation">
    @@ -160,41 +141,25 @@
                 <article class="md-content__inner md-typeset">
                   {% block content %}
                     {% if page.edit_url %}
    -                  <a href="{{ page.edit_url }}" title="{{ lang.t('edit.link.title') }}" class="md-icon md-content__icon">&#xE3C9;</a>
    +                  <a href="{{ page.edit_url }}" title="{{ lang.t('edit.link.title') }}" class="md-content__button md-icon">
    +                    {% include ".icons/material/pencil.svg" %}
    +                  </a>
                     {% endif %}
    +                {% block source %}
    +                  {% if page and page.meta and page.meta.source %}
    +                    {% include "partials/source-link.html" %}
    +                  {% endif %}
    +                {% endblock %}
                     {% if not "\x3ch1" in page.content %}
                       <h1>{{ page.title | default(config.site_name, true)}}</h1>
                     {% endif %}
                     {{ page.content }}
    -                {% block source %}
    -                  {% if page and page.meta and page.meta.source %}
    -                    <h2 id="__source">{{ lang.t("meta.source") }}</h2>
    -                    {% set repo = config.repo_url %}
    -                    {% if repo | last == "/" %}
    -                      {% set repo = repo[:-1] %}
    -                    {% endif %}
    -                    {% set path = page.meta.path | default([""]) %}
    -                    {% set file = page.meta.source %}
    -                    <a href="{{ [repo, path, file] | join('/') }}" title="{{ file }}" class="md-source-file">
    -                      {{ file }}
    -                    </a>
    -                  {% endif %}
    -                {% endblock %}
    +                {% if page and page.meta %}
    +                  {% if page.meta.git_revision_date_localized or
    +                        page.meta.revision_date
    +                  %}
    +                    {% include "partials/source-date.html" %}
    -                {% if page and page.meta and (
    -                      page.meta.git_revision_date_localized or
    -                      page.meta.revision_date
    -                ) %}
    -                  {% set label = lang.t("source.revision.date") %}
    -                  <hr>
    -                  <div class="md-source-date">
    -                    <small>
    -                      {% if page.meta.git_revision_date_localized %}
    -                        {{ label }}: {{ page.meta.git_revision_date_localized }}
    -                      {% elif page.meta.revision_date %}
    -                        {{ label }}: {{ page.meta.revision_date }}
    -                      {% endif %}
    -                    </small>
    -                  </div>
                     {% endif %}
                   {% endblock %}
                   {% block disqus %}
    @@ -208,29 +174,35 @@
             {% include "partials/footer.html" %}
           {% endblock %}
         </div>
         {% block scripts %}
    -      <script src="{{ 'assets/javascripts/application.********.js' | url }}"></script>
    -      {% if lang.t("search.language") != "en" %}
    -        {% set languages = lang.t("search.language").split(",") %}
    -        {% if languages | length and languages[0] != "" %}
    -          {% set path = "assets/javascripts/lunr/" %}
    -          <script src="{{ (path ~ 'lunr.stemmer.support.js') | url }}"></script>
    -          {% for language in languages | map("trim") %}
    -            {% if language != "en" %}
    -              {% if language == "ja" %}
    -                <script src="{{ (path ~ 'tinyseg.js') | url }}"></script>
    -              {% endif %}
    -              {% if language in ("ar", "da", "de", "es", "fi", "fr", "hu", "it", "ja", "nl", "no", "pt", "ro", "ru", "sv", "th", "tr", "vi") %}
    -                <script src="{{ (path ~ 'lunr.' ~ language ~ '.js') | url }}"></script>
    -              {% endif %}
    -            {% endif %}
    -          {% endfor %}
    -          {% if languages | length > 1 %}
    -            <script src="{{ (path ~ 'lunr.multi.js') | url }}"></script>
    -          {% endif %}
    -        {% endif %}
    -      {% endif %}
    -      <script>app.initialize({version:"{{ mkdocs_version }}",url:{base:"{{ base_url }}"}})</script>
    +      <script src="{{ 'assets/javascripts/vendor.********.min.js' | url }}"></script>
    +      <script src="{{ 'assets/javascripts/bundle.********.min.js' | url }}"></script>
    +      {%- set translations = {} -%}
    +      {%- for key in [
    +        "clipboard.copy",
    +        "clipboard.copied",
    +        "search.config.lang",
    +        "search.config.pipeline",
    +        "search.config.separator",
    +        "search.result.placeholder",
    +        "search.result.none",
    +        "search.result.one",
    +        "search.result.other"
    +      ] -%}
    +        {%- set _ = translations.update({ key: lang.t(key) }) -%}
    +      {%- endfor -%}
    +      <script id="__lang" type="application/json">
    +        {{- translations | tojson -}}
    +      </script>
    +      {% block config %}{% endblock %}
    +      <script>
    +        app = initialize({
    +          base: "{{ base_url }}",
    +          features: {{ config.theme.features | tojson }},
    +          search: Object.assign({
    +            worker: "{{ 'assets/javascripts/worker/search.********.min.js' | url }}"
    +          }, typeof search !== "undefined" && search)
    +        })
    +      </script>
           {% for path in config["extra_javascript"] %}
             <script src="{{ path | url }}"></script>
           {% endfor %}
    ```

=== ":octicons-file-code-16: `partials/footer.html`"

    ``` diff
    @@ -5,34 +5,34 @@
         <div class="md-footer-nav">
    -      <nav class="md-footer-nav__inner md-grid">
    +      <nav class="md-footer-nav__inner md-grid" aria-label="{{ lang.t('footer.title') }}">
             {% if page.previous_page %}
    -          <a href="{{ page.previous_page.url | url }}" title="{{ page.previous_page.title | striptags }}" class="md-flex md-footer-nav__link md-footer-nav__link--prev" rel="prev">
    -            <div class="md-flex__cell md-flex__cell--shrink">
    -              <i class="md-icon md-icon--arrow-back md-footer-nav__button"></i>
    +          <a href="{{ page.previous_page.url | url }}" title="{{ page.previous_page.title | striptags }}" class="md-footer-nav__link md-footer-nav__link--prev" rel="prev">
    +            <div class="md-footer-nav__button md-icon">
    +              {% include ".icons/material/arrow-left.svg" %}
                 </div>
    -            <div class="md-flex__cell md-flex__cell--stretch md-footer-nav__title">
    -              <span class="md-flex__ellipsis">
    +            <div class="md-footer-nav__title">
    +              <div class="md-ellipsis">
                     <span class="md-footer-nav__direction">
                       {{ lang.t("footer.previous") }}
                     </span>
                     {{ page.previous_page.title }}
    -              </span>
    +              </div>
                 </div>
               </a>
             {% endif %}
             {% if page.next_page %}
    -          <a href="{{ page.next_page.url | url }}" title="{{ page.next_page.title | striptags }}" class="md-flex md-footer-nav__link md-footer-nav__link--next" rel="next">
    -            <div class="md-flex__cell md-flex__cell--stretch md-footer-nav__title">
    -              <span class="md-flex__ellipsis">
    +          <a href="{{ page.next_page.url | url }}" title="{{ page.next_page.title | striptags }}" class="md-footer-nav__link md-footer-nav__link--next" rel="next">
    +            <div class="md-footer-nav__title">
    +              <div class="md-ellipsis">
                     <span class="md-footer-nav__direction">
                       {{ lang.t("footer.next") }}
                     </span>
                     {{ page.next_page.title }}
    -              </span>
    +              </div>
                 </div>
    -            <div class="md-flex__cell md-flex__cell--shrink">
    -              <i class="md-icon md-icon--arrow-forward md-footer-nav__button"></i>
    +            <div class="md-footer-nav__button md-icon">
    +              {% include ".icons/material/arrow-right.svg" %}
                 </div>
               </a>
             {% endif %}
    ```

=== ":octicons-file-code-16: `partials/header.html`"

    ``` diff
    @@ -4,51 +4,43 @@
     <header class="md-header" data-md-component="header">
    -  <nav class="md-header-nav md-grid">
    -    <div class="md-flex">
    -      <div class="md-flex__cell md-flex__cell--shrink">
    -        <a href="{{ config.site_url | default(nav.homepage.url, true) | url }}" title="{{ config.site_name }}" aria-label="{{ config.site_name }}" class="md-header-nav__button md-logo">
    -          {% if config.theme.logo.icon %}
    -            <i class="md-icon">{{ config.theme.logo.icon }}</i>
    -          {% else %}
    -            <img alt="logo" src="{{ config.theme.logo | url }}" width="24" height="24">
    -          {% endif %}
    -        </a>
    -      </div>
    -      <div class="md-flex__cell md-flex__cell--shrink">
    -        <label class="md-icon md-icon--menu md-header-nav__button" for="__drawer"></label>
    -      </div>
    -      <div class="md-flex__cell md-flex__cell--stretch">
    -        <div class="md-flex__ellipsis md-header-nav__title" data-md-component="title">
    -          {% if config.site_name == page.title %}
    -            {{ config.site_name }}
    -          {% else %}
    -            <span class="md-header-nav__topic">
    -              {{ config.site_name }}
    -            </span>
    -            <span class="md-header-nav__topic">
    -              {% if page and page.meta and page.meta.title %}
    -                {{ page.meta.title }}
    -              {% else %}
    -                {{ page.title }}
    -              {% endif %}
    -            </span>
    -          {% endif %}
    +  <nav class="md-header-nav md-grid" aria-label="{{ lang.t('header.title') }}">
    +    <a href="{{ config.site_url | default(nav.homepage.url, true) | url }}" title="{{ config.site_name }}" class="md-header-nav__button md-logo" aria-label="{{ config.site_name }}">
    +      {% include "partials/logo.html" %}
    +    </a>
    +    <label class="md-header-nav__button md-icon" for="__drawer">
    +      {% include ".icons/material/menu" ~ ".svg" %}
    +    </label>
    +    <div class="md-header-nav__title" data-md-component="header-title">
    +      {% if config.site_name == page.title %}
    +        <div class="md-header-nav__ellipsis md-ellipsis">
    +          {{ config.site_name }}
             </div>
    -      </div>
    -      <div class="md-flex__cell md-flex__cell--shrink">
    -        {% if "search" in config["plugins"] %}
    -          <label class="md-icon md-icon--search md-header-nav__button" for="__search"></label>
    -          {% include "partials/search.html" %}
    -        {% endif %}
    -      </div>
    -      {% if config.repo_url %}
    -        <div class="md-flex__cell md-flex__cell--shrink">
    -          <div class="md-header-nav__source">
    -            {% include "partials/source.html" %}
    -          </div>
    +      {% else %}
    +        <div class="md-header-nav__ellipsis">
    +          <span class="md-header-nav__topic md-ellipsis">
    +            {{ config.site_name }}
    +          </span>
    +          <span class="md-header-nav__topic md-ellipsis">
    +            {% if page and page.meta and page.meta.title %}
    +              {{ page.meta.title }}
    +            {% else %}
    +              {{ page.title }}
    +            {% endif %}
    +          </span>
             </div>
           {% endif %}
         </div>
    +    {% if "search" in config["plugins"] %}
    +      <label class="md-header-nav__button md-icon" for="__search">
    +        {% include ".icons/material/magnify.svg" %}
    +      </label>
    +      {% include "partials/search.html" %}
    +    {% endif %}
    +    {% if config.repo_url %}
    +      <div class="md-header-nav__source">
    +        {% include "partials/source.html" %}
    +      </div>
    +    {% endif %}
       </nav>
     </header>
    ```

=== ":octicons-file-code-16: `partials/hero.html`"

    ``` diff
    @@ -4,9 +4,8 @@
    -{% set feature = config.theme.feature %}
     {% set class = "md-hero" %}
    -{% if not feature.tabs %}
    +{% if "tabs" not in config.theme.features %}
       {% set class = "md-hero md-hero--expand" %}
     {% endif %}
     <div class="{{ class }}" data-md-component="hero">
    ```

=== ":octicons-file-code-16: `partials/language.html`"

    ``` diff
    @@ -4,12 +4,4 @@
     {% import "partials/language/" + config.theme.language + ".html" as lang %}
     {% import "partials/language/en.html" as fallback %}
    -{% macro t(key) %}{{ {
    -  "direction": config.theme.direction,
    -  "search.language": (
    -    config.extra.search | default({})
    -  ).language,
    -  "search.tokenizer": (
    -    config.extra.search | default({})
    -  ).tokenizer | default("", true),
    -}[key] or lang.t(key) or fallback.t(key) }}{% endmacro %}
    +{% macro t(key) %}{{ lang.t(key) | default(fallback.t(key)) }}{% endmacro %}
    ```

=== ":octicons-file-code-16: `partials/logo.html`"

    ``` diff
    @@ -0,0 +1,9 @@
    +{#-
    +  This file was automatically generated - do not edit
    +-#}
    +{% if config.theme.logo %}
    +  <img src="{{ config.theme.logo | url }}" alt="logo">
    +{% else %}
    +  {% set icon = config.theme.icon.logo or "material/library" %}
    +  {% include ".icons/" ~ icon ~ ".svg" %}
    +{% endif %}
    ```

=== ":octicons-file-code-16: `partials/nav-item.html`"

    ``` diff
    @@ -14,9 +14,15 @@
         {% endif %}
         <label class="md-nav__link" for="{{ path }}">
           {{ nav_item.title }}
    +      <span class="md-nav__icon md-icon">
    +        {% include ".icons/material/chevron-right.svg" %}
    +      </span>
         </label>
    -    <nav class="md-nav" data-md-component="collapsible" data-md-level="{{ level }}">
    +    <nav class="md-nav" aria-label="{{ nav_item.title }}" data-md-level="{{ level }}">
           <label class="md-nav__title" for="{{ path }}">
    +        <span class="md-nav__icon md-icon">
    +          {% include ".icons/material/arrow-left.svg" %}
    +        </span>
             {{ nav_item.title }}
           </label>
           <ul class="md-nav__list" data-md-scrollfix>
    @@ -39,6 +45,9 @@
         {% if toc | first is defined %}
           <label class="md-nav__link md-nav__link--active" for="__toc">
             {{ nav_item.title }}
    +        <span class="md-nav__icon md-icon">
    +          {% include ".icons/material/table-of-contents.svg" %}
    +        </span>
           </label>
         {% endif %}
         <a href="{{ nav_item.url | url }}" title="{{ nav_item.title | striptags }}" class="md-nav__link md-nav__link--active">
    ```

=== ":octicons-file-code-16: `partials/nav.html`"

    ``` diff
    @@ -4,14 +4,10 @@
    -<nav class="md-nav md-nav--primary" data-md-level="0">
    -  <label class="md-nav__title md-nav__title--site" for="__drawer">
    -    <a href="{{ config.site_url | default(nav.homepage.url, true) | url }}" title="{{ config.site_name }}" class="md-nav__button md-logo">
    -      {% if config.theme.logo.icon %}
    -        <i class="md-icon">{{ config.theme.logo.icon }}</i>
    -      {% else %}
    -        <img alt="logo" src="{{ config.theme.logo | url }}" width="48" height="48">
    -      {% endif %}
    +<nav class="md-nav md-nav--primary" aria-label="{{ lang.t('nav.title') }}" data-md-level="0">
    +  <label class="md-nav__title" for="__drawer">
    +    <a href="{{ config.site_url | default(nav.homepage.url, true) | url }}" title="{{ config.site_name }}" class="md-nav__button md-logo" aria-label="{{ config.site_name }}">
    +      {% include "partials/logo.html" %}
         </a>
         {{ config.site_name }}
       </label>
    ```

=== ":octicons-file-code-16: `partials/search.html`"

    ``` diff
    @@ -6,15 +6,18 @@
       <label class="md-search__overlay" for="__search"></label>
       <div class="md-search__inner" role="search">
         <form class="md-search__form" name="search">
    -      <input type="text" class="md-search__input" name="query" aria-label="Search" placeholder="{{ lang.t('search.placeholder') }}" autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false" data-md-component="query" data-md-state="active">
    +      <input type="text" class="md-search__input" name="query" aria-label="{{ lang.t('search.placeholder') }}" placeholder="{{ lang.t('search.placeholder') }}" autocapitalize="off" autocorrect="off" autocomplete="off" spellcheck="false" data-md-component="search-query" data-md-state="active">
           <label class="md-search__icon md-icon" for="__search">
    +        {% include ".icons/material/magnify.svg" %}
    +        {% include ".icons/material/arrow-left.svg" %}
           </label>
    -      <button type="reset" class="md-icon md-search__icon" data-md-component="reset" tabindex="-1">
    -        &#xE5CD;
    +      <button type="reset" class="md-search__icon md-icon" aria-label="{{ lang.t('search.reset') }}" data-md-component="search-reset" tabindex="-1">
    +        {% include ".icons/material/close.svg" %}
           </button>
         </form>
         <div class="md-search__output">
           <div class="md-search__scrollwrap" data-md-scrollfix>
    -        <div class="md-search-result" data-md-component="result">
    +        <div class="md-search-result" data-md-component="search-result">
               <div class="md-search-result__meta">
                 {{ lang.t("search.result.placeholder") }}
               </div>
    ```

=== ":octicons-file-code-16: `partials/social.html`"

    ``` diff
    @@ -4,9 +4,12 @@
     {% if config.extra.social %}
       <div class="md-footer-social">
    -    <link rel="stylesheet" href="{{ 'assets/fonts/font-awesome.css' | url }}">
         {% for social in config.extra.social %}
    -      <a href="{{ social.link }}" target="_blank" rel="noopener" title="{{ social.type }}" class="md-footer-social__link fa fa-{{ social.type }}"></a>
    +      {% set _,rest = social.link.split("//") %}
    +      {% set domain = rest.split("/")[0] %}
    +      <a href="{{ social.link }}" target="_blank" rel="noopener" title="{{ domain }}" class="md-footer-social__link">
    +        {% include ".icons/" ~ social.icon ~ ".svg" %}
    +      </a>
         {% endfor %}
       </div>
     {% endif %}
    ```

=== ":octicons-file-code-16: `partials/source-date.html`"

    ``` diff
    @@ -0,0 +1,15 @@
    +{#-
    +  This file was automatically generated - do not edit
    +-#}
    +{% import "partials/language.html" as lang with context %}
    +{% set label = lang.t("source.revision.date") %}
    +<hr>
    +<div class="md-source-date">
    +  <small>
    +    {% if page.meta.git_revision_date_localized %}
    +      {{ label }}: {{ page.meta.git_revision_date_localized }}
    +    {% elif page.meta.revision_date %}
    +      {{ label }}: {{ page.meta.revision_date }}
    +    {% endif %}
    +  </small>
    +</div>
    ```

=== ":octicons-file-code-16: `partials/source-link.html`"

    ``` diff
    @@ -0,0 +1,13 @@
    +{#-
    +  This file was automatically generated - do not edit
    +-#}
    +{% import "partials/language.html" as lang with context %}
    +{% set repo = config.repo_url %}
    +{% if repo | last == "/" %}
    +  {% set repo = repo[:-1] %}
    +{% endif %}
    +{% set path = page.meta.path | default([""]) %}
    +<a href="{{ [repo, path, page.meta.source] | join('/') }}" title="{{ file }}" class="md-content__button md-icon">
    +  {{ lang.t("meta.source") }}
    +  {% include ".icons/" ~ config.theme.icon.repo ~ ".svg" %}
    +</a>
    ```

=== ":octicons-file-code-16: `partials/source.html`"

    ``` diff
    @@ -4,24 +4,11 @@
     {% import "partials/language.html" as lang with context %}
    -{% set platform = config.extra.repo_icon or config.repo_url %}
    -{% if "github" in platform %}
    -  {% set repo_type = "github" %}
    -{% elif "gitlab" in platform %}
    -  {% set repo_type = "gitlab" %}
    -{% elif "bitbucket" in platform %}
    -  {% set repo_type = "bitbucket" %}
    -{% else %}
    -  {% set repo_type = "" %}
    -{% endif %}
    -<a href="{{ config.repo_url }}" title="{{ lang.t('source.link.title') }}" class="md-source" data-md-source="{{ repo_type }}">
    -  {% if repo_type %}
    -    <div class="md-source__icon">
    -      <svg viewBox="0 0 24 24" width="24" height="24">
    -        <use xlink:href="#__{{ repo_type }}" width="24" height="24"></use>
    -      </svg>
    -    </div>
    -  {% endif %}
    +<a href="{{ config.repo_url }}" title="{{ lang.t('source.link.title') }}" class="md-source">
    +  <div class="md-source__icon md-icon">
    +    {% set icon = config.theme.icon.repo or "fontawesome/brands/git-alt" %}
    +    {% include ".icons/" ~ icon ~ ".svg" %}
    +  </div>
       <div class="md-source__repository">
         {{ config.repo_name }}
       </div>
    ```

=== ":octicons-file-code-16: `partials/tabs-item.html`"

    ``` diff
    @@ -4,7 +4,7 @@
    -{% if nav_item.is_homepage %}
    +{% if nav_item.is_homepage or nav_item.url == "index.html" %}
       <li class="md-tabs__item">
         {% if not page.ancestors | length and nav | selectattr("url", page.url) %}
           <a href="{{ nav_item.url | url }}" class="md-tabs__link md-tabs__link--active">
    ```

=== ":octicons-file-code-16: `partials/tabs.html`"

    ``` diff
    @@ -5,7 +5,7 @@
     {% if page.ancestors | length > 0 %}
       {% set class = "md-tabs md-tabs--active" %}
     {% endif %}
    -<nav class="{{ class }}" data-md-component="tabs">
    +<nav class="{{ class }}" aria-label="{{ lang.t('tabs.title') }}" data-md-component="tabs">
       <div class="md-tabs__inner md-grid">
         <ul class="md-tabs__list">
           {% for nav_item in nav %}
    ```

=== ":octicons-file-code-16: `partials/toc-item.html`"

    ``` diff
    @@ -6,7 +6,7 @@
         {{ toc_item.title }}
       </a>
       {% if toc_item.children %}
    -    <nav class="md-nav">
    +    <nav class="md-nav" aria-label="{{ toc_item.title }}">
           <ul class="md-nav__list">
             {% for toc_item in toc_item.children %}
               {% include "partials/toc-item.html" %}
    ```

=== ":octicons-file-code-16: `partials/toc.html`"

    ``` diff
    @@ -4,35 +4,22 @@
     {% import "partials/language.html" as lang with context %}
    -<nav class="md-nav md-nav--secondary">
    +<nav class="md-nav md-nav--secondary" aria-label="{{ lang.t('toc.title') }}">
       {% endif %}
       {% if toc | first is defined %}
         <label class="md-nav__title" for="__toc">
    +      <span class="md-nav__icon md-icon">
    +        {% include ".icons/material/arrow-left.svg" %}
    +      </span>
           {{ lang.t("toc.title") }}
         </label>
         <ul class="md-nav__list" data-md-scrollfix>
           {% for toc_item in toc %}
             {% include "partials/toc-item.html" %}
           {% endfor %}
    -      {% if page.meta.source and page.meta.source | length > 0 %}
    -        <li class="md-nav__item">
    -          <a href="#__source" class="md-nav__link md-nav__link--active">
    -            {{ lang.t("meta.source") }}
    -          </a>
    -        </li>
    -      {% endif %}
    -      {% set disqus = config.extra.disqus %}
    -      {% if page and page.meta and page.meta.disqus is string %}
    -        {% set disqus = page.meta.disqus %}
    -      {% endif %}
    -      {% if not page.is_homepage and disqus %}
    -        <li class="md-nav__item">
    -          <a href="#__comments" class="md-nav__link md-nav__link--active">
    -            {{ lang.t("meta.comments") }}
    -          </a>
    -        </li>
    -      {% endif %}
         </ul>
       {% endif %}
     </nav>
    ```

## Upgrading from 3.x to 4.x

### What's new?

Material for MkDocs 4 fixes incorrect layout on Chinese systems. The fix
includes a mandatory change of the base font-size from `10px` to `20px` which
means all `rem` values needed to be updated. Within the theme, `px` to `rem`
calculation is now encapsulated in a new function called `px2rem` which is part
of the SASS code base.

If you use Material for MkDocs with custom CSS that is based on `rem` values,
note that those values must now be divided by 2. Now, `1.0rem` doesn't map to
`10px`, but `20px`. To learn more about the problem and implications, please
refer to #911 in which the problem was discovered and fixed.

### Changes to `mkdocs.yml`

None.

### Changes to `*.html` files

None.
````
