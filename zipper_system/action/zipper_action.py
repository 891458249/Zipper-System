# -*- coding: utf-8 -*-
"""ZipperAction -- the framework-facing wrapper (ARCHITECTURE.md sec.10 P2).

A thin, dependency-light facade adapting the new ``rig_spec`` (sec.C) so the
tool can be driven from a shelf button, a menu, a script, or an external
ActionCore-style framework, without those callers needing to know the build /
ui module layout. No Qt import at module load (the UI is imported lazily).
"""

# Python 3.7-common syntax only.


class ZipperAction(object):
    """Facade over validate / build / UI for the Zipper System."""

    label = "Zipper System"
    name = "zipperSystem"

    # -- headless API ------------------------------------------------------ #
    @staticmethod
    def validate(rig_spec):
        """Validate a rig_spec; returns a build.validate.ValidationReport."""
        from ..build.validate import validate as _validate
        return _validate(rig_spec)

    @staticmethod
    def build(rig_spec):
        """Validate then build; returns the rig-root node name.

        Raises build.zipper_builder.ZipperValidationError on bad input (before
        any scene change) or re-raises a rolled-back build error.
        """
        from ..build import zipper_builder
        return zipper_builder.build(rig_spec)

    # -- interactive ------------------------------------------------------- #
    @staticmethod
    def show_ui():
        """Open the Zipper System panel (lazy Qt import)."""
        from ..ui import show
        return show()

    # -- convenience: run from a shelf/menu -------------------------------- #
    def __call__(self):
        return self.show_ui()


def run():
    """Module-level shortcut for shelf buttons: ``zipper_action.run()``."""
    return ZipperAction().show_ui()
