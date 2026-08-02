;;; guix.scm — package definition for pic itself.
;;;
;;; Following the project convention: this file evaluates to a package,
;;; so `guix shell -D -f guix.scm` provides a development environment
;;; (python, pytest) for working on pic.
;;;
;;; The source is the checkout itself; the repository has no .git, so
;;; the whole directory is copied with local-file.

(use-modules (gnu packages check)
             (gnu packages python-build)
             (gnu packages rust-apps)
             (guix build-system pyproject)
             (guix gexp)
             (guix packages)
             ((guix licenses) #:prefix license:))

(package
  (name "pic")
  (version "0.1.0")
  (source (local-file "." "pic" #:recursive? #t))
  (build-system pyproject-build-system)
  (native-inputs (list python-pytest python-setuptools python-wheel uv))
  (home-page "https://example.org/pic")
  (synopsis "Run the pi coding agent inside a container")
  (description
   "pic runs the pi coding agent in a container (guix shell -C or an OCI
runtime).  It owns the arguments before a
bare @code{--}; everything after goes verbatim to the inner command.")
  (license license:expat))
