// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import java.util.Objects;
import org.fireflyframework.koinon.sdk.RequestOptions;

public record SourceFolderFilter(String driveId,String folderId,String cursor) {
public static SourceFolderFilter empty(){return new SourceFolderFilter(null,null,null);}
public SourceFolderFilter withDriveId(String value){return new SourceFolderFilter(value,folderId,cursor);}
public SourceFolderFilter withFolderId(String value){return new SourceFolderFilter(driveId,value,cursor);}
public SourceFolderFilter withCursor(String value){return new SourceFolderFilter(driveId,folderId,value);}
public RequestOptions applyTo(RequestOptions options){
Objects.requireNonNull(driveId,"drive_id is required");
if(driveId!=null)options=options.query("drive_id",String.valueOf(driveId));
if(folderId!=null)options=options.query("folder_id",String.valueOf(folderId));
if(cursor!=null)options=options.query("cursor",String.valueOf(cursor));
return options;}
}
