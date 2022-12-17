To release a new version of ate-dispatcher:

1. git fetch upstream && git checkout upstream/main
2. Close milestone on GitHub
3. git clean -xfdi
4. Update CHANGELOG.md with git-cliff (git cliff --tag X.X.X)
5. git add -A && git commit -m "Update Changelog"
6. Update release version in ``__init__.py`` (set release version, remove 'dev')
8. git add -A && git commit -m "Release vX.X.X"
9. git tag -a vX.X.X -m "Release vX.X.X"
14. python setup.py sdist
15. python setup.py bdist_wheel
10. Update development version in ``Update Changelog`` (add '-dev' and increment minor version)
11. git add -A && git commit -m "Set development version to vY.Y.Y"
12. git push upstream main
13. git push upstream --tags
16. twine upload dist/*
