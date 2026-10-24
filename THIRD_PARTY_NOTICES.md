# Third-party software

The local web application uses React Flow (@xyflow/react, MIT), React (MIT), Radix UI (MIT), react-resizable-panels (MIT), Lucide (ISC), Tailwind CSS (MIT) and the runtime dependencies listed in `frontend/package-lock.json`. Button and Tabs source components adapt shadcn/ui under the MIT license; its complete notice is in `frontend/licenses/shadcn-ui.txt`.

`npm run build --prefix frontend` generates `web/third-party-licenses.txt` from the pinned production dependency packages. That file includes package names, versions, licenses and complete available copyright/license notices. It is included in the Windows offline package and available locally at `/static/third-party-licenses.txt`. No frontend CDN or runtime package download is used. The archived Deep Agents UI was only a design reference; its code is not incorporated.

Python dependencies are pinned in `requirements-windows.lock`. Their installed distribution metadata and bundled license files remain in `python/Lib/site-packages` in the offline distribution. CPython's embedded distribution retains its LICENSE.txt. The offline bundle is built from official CPython and Windows wheels, not from a macOS virtual environment.
