document.addEventListener("DOMContentLoaded", function() {
  // Reading Progress Bar
  const progressBar = document.getElementById("reading-progress-bar");

  if (progressBar) {
    window.addEventListener("scroll", function() {
      const scrollTop = document.documentElement.scrollTop;
      const scrollHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrollProgress = (scrollTop / scrollHeight) * 100;
      progressBar.style.width = scrollProgress + "%";
    });
  }

  // Home Page View Toggle
  const cardViewBtn = document.getElementById("card-view-btn");
  const listViewBtn = document.getElementById("list-view-btn");
  const postList = document.getElementById("post-list");

  if (cardViewBtn && listViewBtn && postList) {
    cardViewBtn.addEventListener("click", function() {
      postList.classList.remove("list-view");
      postList.classList.add("card-view");
      cardViewBtn.classList.add("active");
      listViewBtn.classList.remove("active");
      cardViewBtn.setAttribute("aria-pressed", "true");
      listViewBtn.setAttribute("aria-pressed", "false");
    });

    listViewBtn.addEventListener("click", function() {
      postList.classList.remove("card-view");
      postList.classList.add("list-view");
      listViewBtn.classList.add("active");
      cardViewBtn.classList.remove("active");
      listViewBtn.setAttribute("aria-pressed", "true");
      cardViewBtn.setAttribute("aria-pressed", "false");
    });
  }
});
