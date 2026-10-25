#!/usr/bin/env python3
"""Crea el repositorio público y activa GitHub Pages usando GitHub CLI."""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args, capture=False, check=True):
    return subprocess.run(args, cwd=ROOT, text=True, check=check,
                          stdout=subprocess.PIPE if capture else None,
                          stderr=subprocess.PIPE if capture else None)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--nombre', default='ofertas-switch')
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,99}', args.nombre):
        ap.error('Nombre de repositorio no válido')
    for executable in ('gh', 'git'):
        if not shutil.which(executable):
            raise ValueError(f'Instala {executable} antes de continuar. GitHub CLI: https://cli.github.com/')
    if run('gh','auth','status',capture=True,check=False).returncode:
        run('gh','auth','login','--web','--git-protocol','https')
    login = json.loads(run('gh','api','user',capture=True).stdout)['login']
    repo = f'{login}/{args.nombre}'
    exists = run('gh','repo','view',repo,'--json','nameWithOwner',capture=True,check=False).returncode == 0
    if (ROOT/'.git').exists():
        remote = run('git','remote','get-url','origin',capture=True,check=False)
        if remote.returncode or remote.stdout.strip() not in (f'https://github.com/{repo}.git',f'https://github.com/{repo}',f'git@github.com:{repo}.git'):
            raise ValueError('La carpeta ya pertenece a otro repositorio. Usa una copia nueva del ZIP.')
        if not exists:
            raise ValueError('El repositorio configurado ya no está accesible')
    else:
        if exists:
            raise ValueError(f'{repo} ya existe. Usa --nombre otro-nombre; no se sobrescribe.')
        run('git','init','-b','main')
        # Identidad local exclusiva de este proyecto.
        run('git','config','user.name',login)
        run('git','config','user.email',f'{login}@users.noreply.github.com')
        run('git','add','scraper.py','test_scraper.py','test_publicacion.py','preparar_web.py','publicar.py','README.md','.gitignore','.github')
        run('git','commit','-m','Configurar ofertas de Switch y despliegue automático')
        run('gh','auth','setup-git')
        run('gh','repo','create',repo,'--public','--source','.','--remote','origin','--push',
            '--description','Ofertas de juegos Nintendo Switch y Switch 2 en MediaMarkt España')
    endpoint = f'repos/{repo}/pages'
    pages = run('gh','api',endpoint,capture=True,check=False)
    if pages.returncode:
        if '404' not in pages.stderr:
            raise ValueError('No se puede consultar Pages: '+pages.stderr.strip())
        run('gh','api','--method','POST',endpoint,'-f','build_type=workflow')
    else:
        config = json.loads(pages.stdout)
        if config.get('build_type') != 'workflow':
            run('gh','api','--method','PUT',endpoint,'-f','build_type=workflow')
    # Inicia una actualización después de habilitar Pages.
    run('gh','workflow','run','ofertas.yml','--repo',repo,'--ref','main')
    print(f'Configuración completada. Estado: https://github.com/{repo}/actions')
    print(f'Cuando termine correctamente: https://{login}.github.io/{args.nombre}/')
    print('La publicación no se considera verificada hasta que el workflow finalice.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f'No se ha completado la configuración: {exc}',file=sys.stderr)
        sys.exit(1)
