!macro customInstall
  IfFileExists "$INSTDIR\resources\vc_redist.x64.exe" 0 vcDone
  DetailPrint "Installing Microsoft Visual C++ runtime (required by MySQL)..."
  ExecWait '"$INSTDIR\resources\vc_redist.x64.exe" /install /quiet /norestart'
  vcDone:
!macroend

!macro customUnInstall
!macroend
