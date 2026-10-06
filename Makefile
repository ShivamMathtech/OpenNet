.PHONY: setup build test demo clean
setup:
	bash scripts/setup.sh
build:
	bash scripts/build.sh
test:
	bash scripts/test.sh
demo: build
	bash scripts/start_demo.sh
clean:
	rm -rf build
