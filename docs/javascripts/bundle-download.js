(function () {
  function setDownloadAttributes(commitIso) {
    var fallbackIso = commitIso || new Date().toISOString();
    var links = document.querySelectorAll('a[data-bundle-name]');
    if (!links.length) return;

    links.forEach(function (link) {
      var bundleName = link.dataset.bundleName;
      if (!bundleName) return;
      var filename = "repomix_egregora_" + bundleName + "_" + fallbackIso + ".md";
      link.setAttribute("download", filename);
    });
  }

  function fetchCommitIso() {
    var metaUrl = new URL('bundles/meta.json', document.baseURI);
    return fetch(metaUrl, { cache: 'no-store' })
      .then(function (response) {
        if (!response.ok) return null;
        return response.json();
      })
      .then(function (data) {
        if (!data || !data.commit_iso) return null;
        return data.commit_iso;
      })
      .catch(function () {
        return null;
      });
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetchCommitIso().then(function (commitIso) {
      setDownloadAttributes(commitIso);
    });
  });
})();
