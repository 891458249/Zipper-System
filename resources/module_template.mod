// ZipperSystem Maya module (pure-Python; identical content for every version).
//
// PATH_TO_MODULE_CONTENT is replaced by the installer with the absolute path of
// the installed module content folder. The same scripts/ + plug-ins/ + icons/
// serve Maya 2022.5 - 2025.3 (the deformer is a pure-Python om2 MPxDeformerNode,
// so there is nothing to recompile per version).
//
//   scripts:   puts the zipper_system package on Maya's Python path
//   plug-ins:  makes the 'zipperSystem' plug-in loadable
//   icons:     shelf / UI icons
//
// This template is for reference / manual installs; the installer generates the
// real .mod dynamically (only the platform + selected versions you install for).

+ MAYAVERSION:2022 PLATFORM:win64 ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2023 PLATFORM:win64 ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2024 PLATFORM:win64 ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2025 PLATFORM:win64 ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons


+ MAYAVERSION:2022 PLATFORM:mac ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2023 PLATFORM:mac ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2024 PLATFORM:mac ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons

+ MAYAVERSION:2025 PLATFORM:mac ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
[r] icons: icons


+ MAYAVERSION:2022 PLATFORM:linux ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
icons: icons

+ MAYAVERSION:2023 PLATFORM:linux ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
icons: icons

+ MAYAVERSION:2024 PLATFORM:linux ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
icons: icons

+ MAYAVERSION:2025 PLATFORM:linux ZipperSystem 0.1.0 PATH_TO_MODULE_CONTENT
scripts: scripts
plug-ins: plug-ins
icons: icons
