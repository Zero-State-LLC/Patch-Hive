// Google Analytics 4. The tag loads only on the production host, so staging and local
// previews never send a measurement. The ID is the only configuration.
var GA_MEASUREMENT_ID = "G-HZYF55H53T";

if (location.hostname === "patch-hive.com") {
  var ga = document.createElement("script");
  ga.async = true;
  ga.src = "https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID;
  document.head.appendChild(ga);
  window.dataLayer = window.dataLayer || [];
  // gtag.js reads the arguments object by index, so this stays a non-arrow function.
  window.gtag = function gtag() {
    window.dataLayer.push(arguments);
  };
  window.gtag("js", new Date());
  window.gtag("config", GA_MEASUREMENT_ID);
}
