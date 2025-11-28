from setuptools import setup, find_packages

setup(
    name='ViralFlow',
    version='1.3.4',
    description='''
    Workflows for viral genome Assembly at FioCruz/IAM
    ''',
    url='https://github.com/dezordi/ViralFlow/',
    author='Antonio Marinho & Filipe Z. Dezordi',
    author_email='amarinhosn@pm.me & zimmer.filipe@gmail.com',
    # aqui é o ponto importante:
    packages=['wrapper'],
    # ou, se quiser algo mais geral:
    # packages=find_packages(include=['wrapper', 'wrapper.*']),
    classifiers=[
        'Programming Language :: Python :: 3.8',
        'Intended Audience :: Science/Research',
        'Topic :: Scientific/Engineering :: Bio-Informatics'
    ],
    scripts=['wrapper/viralflow'],
    zip_safe=False,
)
