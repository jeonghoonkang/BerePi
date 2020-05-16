Option Explicit
Dim myShp As Shape
Dim slide_num As Long
Dim myFont As Variant
Dim msg As Long


Sub catch_font()
myFont = InputBox("*스퀘어*", "글꼴 찾기")
On Error Resume Next
Do While Err.Number = 0
slide_num = slide_num + 1
    For Each myShp In ActivePresentation.Slides(slide_num).Shapes
        If myShp.HasTextFrame = True Then
            If myShp.TextEffect.FontName Like myFont Then
                ActivePresentation.Slides(slide_num).Select
                msg = MsgBox(myShp.TextEffect.FontName & _
                        " 글꼴은" & " " & "현재 " & slide_num & "쪽에 있습니다." & Chr(10) & "검색을 계속 할까요?", vbYesNo)
                    If msg = 7 Then
                    Exit Do
                End If
            End If
        End If
    Next
Loop
slide_num = 0
msg = 0
Set myShp = Nothing


MsgBox "검색을 종료합니다."
On Error GoTo 0

End Sub
