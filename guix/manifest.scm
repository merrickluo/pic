;;; guix/manifest.scm — example agent manifest for the guix backend.
;;;
;;; pic runs the container either from this manifest (project-env mode)
;;; or from a prebuilt profile (profile mode).  This file is an example:
;;; point [backend.guix].manifest at your own manifest to override, and
;;; list the channels that provide your packages under
;;; [backend.guix].channels in ~/.config/pic/pic.toml.
;;;
;;; Adjust the specifications to what your channels provide.

(use-modules (guix profiles))

(specifications->manifest
  (list "pi-coding-agent"
        "python"
        "bash"
        "git"
        "openssh"
        "nss-certs"
        "gnupg"))
