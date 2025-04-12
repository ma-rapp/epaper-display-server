all: png/.stamp

png/.stamp: svg/.stamp
	mkdir -p png
	cd svg; \
	for FILENAME in *.svg; do \
		inkscape $$FILENAME --export-type=png --export-filename=../png/$${FILENAME%.*}.png --export-dpi=300; \
	done
	touch $@

svg/.stamp: weather-icons.zip
	mkdir -p svg
	unzip -j weather-icons.zip "weather-icons-master/svg/*.svg" -d svg
	touch $@

weather-icons.zip:
	wget https://github.com/erikflowers/weather-icons/archive/master.zip -O weather-icons.zip

clean:
	rm -rf svg png
	rm -f weather-icons.zip

.PHONY: all clean
