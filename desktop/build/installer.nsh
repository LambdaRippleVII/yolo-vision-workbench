; YOLO 视觉工作台的安装与卸载选项页。
; 通过 electron-builder 的 custom* 宏接入辅助式 NSIS 安装器。

; electron-builder 会在主模板中稍后再次引入 MUI2；这里提前引入是为了让自定义函数宏可用。
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"

!ifndef BUILD_UNINSTALLER
  ; 安装选项页的窗口句柄。
  Var YoloInstallDialog
  ; 安装选项页的桌面快捷方式复选框。
  Var YoloInstallDesktopShortcut
  ; 安装选项页的开始菜单快捷方式复选框。
  Var YoloInstallStartMenuShortcut
  ; 用户选择的桌面快捷方式状态。
  Var YoloInstallDesktopState
  ; 用户选择的开始菜单快捷方式状态。
  Var YoloInstallStartMenuState
!else
  ; 卸载选项页的窗口句柄。
  Var YoloUninstallDialog
  ; 卸载选项页的删除全部数据选项。
  Var YoloUninstallDeleteAll
  ; 卸载选项页的保留模型与项目选项。
  Var YoloUninstallKeepModels
  ; 卸载选项页的保留全部数据选项。
  Var YoloUninstallKeepAll
  ; 当前卸载操作采用的数据清理模式。
  Var YoloUninstallMode
!endif

!ifndef BUILD_UNINSTALLER
; 安装目录页之后显示快捷方式选择，升级时沿用原有快捷方式设置。
!macro customPageAfterChangeDir
  PageEx custom
    PageCallbacks yoloInstallPageCreate yoloInstallPageLeave
  PageExEnd
!macroend

Function yoloInstallPageCreate
  !insertmacro MUI_HEADER_TEXT "安装选项" "选择快捷方式和后续操作"
  nsDialogs::Create 1018
  Pop $YoloInstallDialog
  ${If} $YoloInstallDialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 28u "YOLO 视觉工作台会安装到你选择的目录。Python 运行环境和模型数据会在首次启动时准备。"
  Pop $0
  ${NSD_CreateGroupBox} 0 42u 100% 78u "快捷方式"
  Pop $0
  ${NSD_CreateCheckbox} 12u 58u 90% 14u "创建桌面快捷方式"
  Pop $YoloInstallDesktopShortcut
  ${NSD_SetState} $YoloInstallDesktopShortcut ${BST_CHECKED}
  ${NSD_CreateCheckbox} 12u 82u 90% 14u "创建开始菜单快捷方式"
  Pop $YoloInstallStartMenuShortcut
  ${NSD_SetState} $YoloInstallStartMenuShortcut ${BST_CHECKED}
  ${NSD_CreateGroupBox} 0 132u 100% 42u "安装完成后"
  Pop $0
  ${NSD_CreateLabel} 12u 148u 90% 20u "可在完成页选择立即启动；也可随时在 Windows 设置中修改或卸载。"
  Pop $0

  nsDialogs::Show
FunctionEnd

Function yoloInstallPageLeave
  ${NSD_GetState} $YoloInstallDesktopShortcut $YoloInstallDesktopState
  ${NSD_GetState} $YoloInstallStartMenuShortcut $YoloInstallStartMenuState
FunctionEnd

; 安装器默认创建快捷方式，用户在选项页取消后在安装结束阶段移除对应链接。
!macro customInstall
  ${If} $YoloInstallDesktopState == 0
    Delete "$newDesktopLink"
  ${EndIf}
  ${If} $YoloInstallStartMenuState == 0
    Delete "$newStartMenuLink"
  ${EndIf}
!macroend
!endif

!ifdef BUILD_UNINSTALLER
; 替换默认卸载欢迎页，先让用户选择数据处理方式。
!macro customUnWelcomePage
  UninstPage custom un.yoloUninstallPageCreate un.yoloUninstallPageLeave
!macroend

; 普通静默卸载默认清理数据；升级流程传入 /KEEP_APP_DATA 时保留数据。
!macro customUnInit
  StrCpy $YoloUninstallMode "all"
  ${GetParameters} $0
  ${GetOptions} $0 "/KEEP_APP_DATA" $1
  ${IfNot} ${Errors}
    StrCpy $YoloUninstallMode "keep-all"
  ${EndIf}
!macroend

Function un.yoloUninstallPageCreate
  !insertmacro MUI_HEADER_TEXT "卸载选项" "选择是否删除本机上的用户数据"
  nsDialogs::Create 1018
  Pop $YoloUninstallDialog
  ${If} $YoloUninstallDialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 38u "卸载程序会移除软件本体。软件数据保存在当前 Windows 账户中，可选择全部删除、只保留模型和项目，或完整保留以便重新安装。"
  Pop $0
  ${NSD_CreateRadioButton} 0 52u 100% 16u "删除当前账户的全部软件数据（模型、项目、环境、设置）"
  Pop $YoloUninstallDeleteAll
  ${NSD_SetState} $YoloUninstallDeleteAll ${BST_CHECKED}
  ${NSD_CreateRadioButton} 0 78u 100% 16u "删除运行环境、日志和缓存；保留模型、项目与设置"
  Pop $YoloUninstallKeepModels
  ${NSD_CreateRadioButton} 0 104u 100% 16u "保留全部软件数据，只卸载程序文件"
  Pop $YoloUninstallKeepAll
  ${NSD_CreateLabel} 0 140u 100% 30u "自定义到其他磁盘或目录的模型、项目不会自动删除。"
  Pop $0

  nsDialogs::Show
FunctionEnd

Function un.yoloUninstallPageLeave
  ${NSD_GetState} $YoloUninstallDeleteAll $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $YoloUninstallMode "all"
    Return
  ${EndIf}
  ${NSD_GetState} $YoloUninstallKeepModels $0
  ${If} $0 == ${BST_CHECKED}
    StrCpy $YoloUninstallMode "keep-models"
    Return
  ${EndIf}
  StrCpy $YoloUninstallMode "keep-all"
FunctionEnd

; 清理 Electron 用户数据目录；仅在卸载页选择后执行，不影响安装目录删除流程。
!macro yoloSetCurrentUserContext
  ${If} $installMode == "all"
    SetShellVarContext current
  ${EndIf}
!macroend

!macro yoloRestoreShellContext
  ${If} $installMode == "all"
    SetShellVarContext all
  ${EndIf}
!macroend

!macro yoloRemoveRuntimeFilesFrom ROOT
  RMDir /r "${ROOT}\python-runtime"
  RMDir /r "${ROOT}\python-runtime.installing"
  RMDir /r "${ROOT}\pip-repair"
  Delete "${ROOT}\get-pip.py"
  RMDir /r "${ROOT}\logs"
  RMDir /r "${ROOT}\Cache"
  RMDir /r "${ROOT}\Code Cache"
  RMDir /r "${ROOT}\GPUCache"
  RMDir /r "${ROOT}\DawnCache"
  RMDir /r "${ROOT}\ShaderCache"
  RMDir /r "${ROOT}\GrShaderCache"
  RMDir /r "${ROOT}\Crashpad"
  RMDir /r "${ROOT}\blob_storage"
!macroend

!macro yoloRemoveRuntimeFiles
  !insertmacro yoloRemoveRuntimeFilesFrom "$APPDATA\${APP_FILENAME}"
  !ifdef APP_PRODUCT_FILENAME
    !insertmacro yoloRemoveRuntimeFilesFrom "$APPDATA\${APP_PRODUCT_FILENAME}"
  !endif
  !insertmacro yoloRemoveRuntimeFilesFrom "$LOCALAPPDATA\${APP_FILENAME}"
  !ifdef APP_PRODUCT_FILENAME
    !insertmacro yoloRemoveRuntimeFilesFrom "$LOCALAPPDATA\${APP_PRODUCT_FILENAME}"
  !endif
  RMDir /r "$TEMP\yolo-vision-workbench"
!macroend

!macro yoloRemoveAllFrom ROOT
  RMDir /r "${ROOT}\${APP_FILENAME}"
  !ifdef APP_PRODUCT_FILENAME
    RMDir /r "${ROOT}\${APP_PRODUCT_FILENAME}"
  !endif
  !ifdef APP_PACKAGE_NAME
    RMDir /r "${ROOT}\${APP_PACKAGE_NAME}"
  !endif
!macroend

!macro yoloRemoveAllUserData
  !insertmacro yoloSetCurrentUserContext
  !insertmacro yoloRemoveAllFrom "$APPDATA"
  !insertmacro yoloRemoveAllFrom "$LOCALAPPDATA"
  RMDir /r "$TEMP\yolo-vision-workbench"
  !ifdef APP_INSTALLER_STORE_FILE
    RMDir /r "$LOCALAPPDATA\${APP_INSTALLER_STORE_FILE}"
  !endif
  !ifdef APP_PACKAGE_STORE_FILE
    RMDir /r "$LOCALAPPDATA\${APP_PACKAGE_STORE_FILE}"
  !endif
  !insertmacro yoloRestoreShellContext
!macroend

!macro customUnInstall
  ; 静默升级不会进入该页面；普通卸载默认选择彻底删除。
  ${If} $YoloUninstallMode == "all"
    !insertmacro yoloRemoveAllUserData
  ${ElseIf} $YoloUninstallMode == "keep-models"
    !insertmacro yoloSetCurrentUserContext
    !insertmacro yoloRemoveRuntimeFiles
    !insertmacro yoloRestoreShellContext
  ${EndIf}
!macroend
!endif
