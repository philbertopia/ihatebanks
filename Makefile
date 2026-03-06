.PHONY: test export-data open-source-check dashboard-install dashboard-build content-seed content-validate content-index

test:
	pytest -q

export-data:
	python scripts/export_dashboard_data.py

open-source-check:
	python scripts/open_source_check.py

dashboard-install:
	cd dashboard && npm install

dashboard-build:
	cd dashboard && npm run build

content-seed:
	cd dashboard && npm run content:seed

content-validate:
	cd dashboard && npm run content:validate

content-index:
	cd dashboard && npm run content:index

