document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("form[data-loading-form]").forEach(function (form) {
    form.addEventListener("submit", function () {
      if (!form.checkValidity()) return;
      var button = form.querySelector('button[type="submit"]');
      if (!button) return;
      button.disabled = true;
      var label = button.querySelector(".button-label");
      var spinner = button.querySelector(".spinner-border");
      if (label) label.textContent = "Analyzing…";
      if (spinner) spinner.classList.remove("d-none");
    });
  });

  document.querySelectorAll("form[novalidate]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });
});
