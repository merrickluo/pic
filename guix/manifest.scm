;;; guix/manifest.scm — example agent manifest for the guix backend.
;;;
;;; pic runs the container either from this manifest (project-env mode)
;;; or from a prebuilt profile (profile mode).  This file is an example:
;;; point [backend.guix].manifest at your own manifest to override, and
;;; list the channels that provide your packages under
;;; [backend.guix].channels in ~/.config/pic/config.toml.
;;;
;;; Adjust the specifications to what your channels provide.

(use-modules (gnu packages)            ; specifications->manifest
             (guix profiles)           ; packages->manifest, concatenate-manifests
             ((gnu packages curl) #:select (curl)))

(concatenate-manifests
 (list (packages->manifest (list curl))
       (specifications->manifest
        (list "pi-coding-agent"
              "python"
              "bash"
              "git"
              "openssh"
              "nss-certs"
              "coreutils"
              "gnupg"
              "fd"
              "ripgrep"
              "mise"))))
