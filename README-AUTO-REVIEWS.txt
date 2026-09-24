AUTOMATIC FUNPAY REVIEWS — Vasya1998

Upload these files/folders to the repository root:
  reviews.json
  reviews-loader.js
  scripts/update_funpay_reviews.py
  .github/workflows/update-funpay-reviews.yml

Then add this line in index.html immediately before the existing <script src="script.js"></script>:
  <script src="reviews-loader.js"></script>

The workflow runs hourly at minute 17 and can also be started manually from Actions.
No FunPay login, password, cookie, golden_key, or other secret is used.

First test:
  GitHub -> Actions -> Update FunPay reviews -> Run workflow
If it is green, reviews.json was fetched and the site will update automatically.
If it fails, open the failed run and share the screenshot/log; FunPay may have changed markup or blocked the GitHub runner.
