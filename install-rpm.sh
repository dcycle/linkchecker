python setup.py install --root=$RPM_BUILD_ROOT --record=INSTALLED_FILES
# 'brp-compress' gzips the man pages without distutils knowing... fix this
sed -i -e 's@man/man\([[:digit:]]\)/\(.\+\.[[:digit:]]\)$@man/man\1/\2.gz@g' INSTALLED_FILES
sed -i -e 's@man/de/man\([[:digit:]]\)/\(.\+\.[[:digit:]]\)$@man/de/man\1/\2.gz@g' INSTALLED_FILES
sed -i -e 's@man/fr/man\([[:digit:]]\)/\(.\+\.[[:digit:]]\)$@man/fr/man\1/\2.gz@g' INSTALLED_FILES
