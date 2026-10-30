// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.api;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import org.fireflyframework.koinon.sdk.*;
import org.fireflyframework.koinon.sdk.internal.Transport;
import org.fireflyframework.koinon.sdk.model.*;

public final class OrganizationPeopleApi {
private final Transport transport; private final String prefix;
public OrganizationPeopleApi(Transport transport,String tenantId){this.transport=Objects.requireNonNull(transport);this.prefix="/tenants/"+Transport.id(tenantId);}
public OrganizationPerson me(OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/people/me",null,options,transport.type(OrganizationPerson.class));}
public OrganizationPerson me(OrganizationScopeFilter filter){return me(filter,RequestOptions.defaults());}
public OrganizationPerson me(){return me(OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> meAsync(OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/people/me",null,options,transport.type(OrganizationPerson.class));}
public CompletableFuture<OrganizationPerson> meAsync(OrganizationScopeFilter filter){return meAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> meAsync(){return meAsync(OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public OrganizationPersonPage list(OrganizationPeopleFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/people",null,options,transport.type(OrganizationPersonPage.class));}
public OrganizationPersonPage list(OrganizationPeopleFilter filter){return list(filter,RequestOptions.defaults());}
public OrganizationPersonPage list(){return list(OrganizationPeopleFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPersonPage> listAsync(OrganizationPeopleFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/people",null,options,transport.type(OrganizationPersonPage.class));}
public CompletableFuture<OrganizationPersonPage> listAsync(OrganizationPeopleFilter filter){return listAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPersonPage> listAsync(){return listAsync(OrganizationPeopleFilter.empty(),RequestOptions.defaults());}
public OrganizationPerson create(OrganizationPersonCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/organization/people",input,options,transport.type(OrganizationPerson.class));}
public OrganizationPerson create(OrganizationPersonCreate input){return create(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> createAsync(OrganizationPersonCreate input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/organization/people",input,options,transport.type(OrganizationPerson.class));}
public CompletableFuture<OrganizationPerson> createAsync(OrganizationPersonCreate input){return createAsync(input,RequestOptions.defaults());}
public OrganizationPerson get(String personId,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/people/"+Transport.id(personId),null,options,transport.type(OrganizationPerson.class));}
public OrganizationPerson get(String personId,OrganizationScopeFilter filter){return get(personId,filter,RequestOptions.defaults());}
public OrganizationPerson get(String personId){return get(personId,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> getAsync(String personId,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/people/"+Transport.id(personId),null,options,transport.type(OrganizationPerson.class));}
public CompletableFuture<OrganizationPerson> getAsync(String personId,OrganizationScopeFilter filter){return getAsync(personId,filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> getAsync(String personId){return getAsync(personId,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public OrganizationPerson update(String personId,OrganizationPersonPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/organization/people/"+Transport.id(personId),input,options,transport.type(OrganizationPerson.class));}
public OrganizationPerson update(String personId,OrganizationPersonPatch input){return update(personId,input,RequestOptions.defaults());}
public CompletableFuture<OrganizationPerson> updateAsync(String personId,OrganizationPersonPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/organization/people/"+Transport.id(personId),input,options,transport.type(OrganizationPerson.class));}
public CompletableFuture<OrganizationPerson> updateAsync(String personId,OrganizationPersonPatch input){return updateAsync(personId,input,RequestOptions.defaults());}
public BinaryResponse avatar(String personId,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.binary("GET",prefix+"/organization/people/"+Transport.id(personId)+"/avatar",options);}
public BinaryResponse avatar(String personId,OrganizationScopeFilter filter){return avatar(personId,filter,RequestOptions.defaults());}
public BinaryResponse avatar(String personId){return avatar(personId,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> avatarAsync(String personId,OrganizationScopeFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.binaryAsync("GET",prefix+"/organization/people/"+Transport.id(personId)+"/avatar",options);}
public CompletableFuture<BinaryResponse> avatarAsync(String personId,OrganizationScopeFilter filter){return avatarAsync(personId,filter,RequestOptions.defaults());}
public CompletableFuture<BinaryResponse> avatarAsync(String personId){return avatarAsync(personId,OrganizationScopeFilter.empty(),RequestOptions.defaults());}
public FileDownload downloadAvatar(String personId,OrganizationScopeFilter filter,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.download("GET",prefix+"/organization/people/"+Transport.id(personId)+"/avatar",target,maxBytes,options);}
public CompletableFuture<FileDownload> downloadAvatarAsync(String personId,OrganizationScopeFilter filter,Path target,long maxBytes,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.downloadAsync("GET",prefix+"/organization/people/"+Transport.id(personId)+"/avatar",target,maxBytes,options);}
public OrganizationPersonPage reports(String personId,OrganizationReportsFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/people/"+Transport.id(personId)+"/reports",null,options,transport.type(OrganizationPersonPage.class));}
public OrganizationPersonPage reports(String personId,OrganizationReportsFilter filter){return reports(personId,filter,RequestOptions.defaults());}
public OrganizationPersonPage reports(String personId){return reports(personId,OrganizationReportsFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationPersonPage> reportsAsync(String personId,OrganizationReportsFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/people/"+Transport.id(personId)+"/reports",null,options,transport.type(OrganizationPersonPage.class));}
public CompletableFuture<OrganizationPersonPage> reportsAsync(String personId,OrganizationReportsFilter filter){return reportsAsync(personId,filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationPersonPage> reportsAsync(String personId){return reportsAsync(personId,OrganizationReportsFilter.empty(),RequestOptions.defaults());}
public OrganizationUnitPage units(OrganizationUnitFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("GET",prefix+"/organization/units",null,options,transport.type(OrganizationUnitPage.class));}
public OrganizationUnitPage units(OrganizationUnitFilter filter){return units(filter,RequestOptions.defaults());}
public OrganizationUnitPage units(){return units(OrganizationUnitFilter.empty(),RequestOptions.defaults());}
public CompletableFuture<OrganizationUnitPage> unitsAsync(OrganizationUnitFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("GET",prefix+"/organization/units",null,options,transport.type(OrganizationUnitPage.class));}
public CompletableFuture<OrganizationUnitPage> unitsAsync(OrganizationUnitFilter filter){return unitsAsync(filter,RequestOptions.defaults());}
public CompletableFuture<OrganizationUnitPage> unitsAsync(){return unitsAsync(OrganizationUnitFilter.empty(),RequestOptions.defaults());}
public OrganizationUnit createUnit(OrganizationUnitInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("POST",prefix+"/organization/units",input,options,transport.type(OrganizationUnit.class));}
public OrganizationUnit createUnit(OrganizationUnitInput input){return createUnit(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationUnit> createUnitAsync(OrganizationUnitInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("POST",prefix+"/organization/units",input,options,transport.type(OrganizationUnit.class));}
public CompletableFuture<OrganizationUnit> createUnitAsync(OrganizationUnitInput input){return createUnitAsync(input,RequestOptions.defaults());}
public OrganizationUnit updateUnit(String unitId,OrganizationUnitPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/organization/units/"+Transport.id(unitId),input,options,transport.type(OrganizationUnit.class));}
public OrganizationUnit updateUnit(String unitId,OrganizationUnitPatch input){return updateUnit(unitId,input,RequestOptions.defaults());}
public CompletableFuture<OrganizationUnit> updateUnitAsync(String unitId,OrganizationUnitPatch input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/organization/units/"+Transport.id(unitId),input,options,transport.type(OrganizationUnit.class));}
public CompletableFuture<OrganizationUnit> updateUnitAsync(String unitId,OrganizationUnitPatch input){return updateUnitAsync(unitId,input,RequestOptions.defaults());}
public Void deleteUnit(String unitId,OrganizationUnitDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.json("DELETE",prefix+"/organization/units/"+Transport.id(unitId),null,options,transport.type(Void.class));}
public Void deleteUnit(String unitId,OrganizationUnitDeleteFilter filter){return deleteUnit(unitId,filter,RequestOptions.defaults());}
public CompletableFuture<Void> deleteUnitAsync(String unitId,OrganizationUnitDeleteFilter filter,RequestOptions options){Objects.requireNonNull(options);options=Objects.requireNonNull(filter).applyTo(options);return transport.jsonAsync("DELETE",prefix+"/organization/units/"+Transport.id(unitId),null,options,transport.type(Void.class));}
public CompletableFuture<Void> deleteUnitAsync(String unitId,OrganizationUnitDeleteFilter filter){return deleteUnitAsync(unitId,filter,RequestOptions.defaults());}
public OrganizationDirectorySettings settings(RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/organization/directory-settings",null,options,transport.type(OrganizationDirectorySettings.class));}
public OrganizationDirectorySettings settings(){return settings(RequestOptions.defaults());}
public CompletableFuture<OrganizationDirectorySettings> settingsAsync(RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/organization/directory-settings",null,options,transport.type(OrganizationDirectorySettings.class));}
public CompletableFuture<OrganizationDirectorySettings> settingsAsync(){return settingsAsync(RequestOptions.defaults());}
public OrganizationDirectorySettings updateSettings(OrganizationDirectorySettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PATCH",prefix+"/organization/directory-settings",input,options,transport.type(OrganizationDirectorySettings.class));}
public OrganizationDirectorySettings updateSettings(OrganizationDirectorySettingsInput input){return updateSettings(input,RequestOptions.defaults());}
public CompletableFuture<OrganizationDirectorySettings> updateSettingsAsync(OrganizationDirectorySettingsInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PATCH",prefix+"/organization/directory-settings",input,options,transport.type(OrganizationDirectorySettings.class));}
public CompletableFuture<OrganizationDirectorySettings> updateSettingsAsync(OrganizationDirectorySettingsInput input){return updateSettingsAsync(input,RequestOptions.defaults());}
public OrganizationProfileMapping mapping(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.json("GET",prefix+"/organization/profile-mappings/"+Transport.id(providerId),null,options,transport.type(OrganizationProfileMapping.class));}
public OrganizationProfileMapping mapping(String providerId){return mapping(providerId,RequestOptions.defaults());}
public CompletableFuture<OrganizationProfileMapping> mappingAsync(String providerId,RequestOptions options){Objects.requireNonNull(options);return transport.jsonAsync("GET",prefix+"/organization/profile-mappings/"+Transport.id(providerId),null,options,transport.type(OrganizationProfileMapping.class));}
public CompletableFuture<OrganizationProfileMapping> mappingAsync(String providerId){return mappingAsync(providerId,RequestOptions.defaults());}
public OrganizationProfileMapping updateMapping(String providerId,OrganizationProfileMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.json("PUT",prefix+"/organization/profile-mappings/"+Transport.id(providerId),input,options,transport.type(OrganizationProfileMapping.class));}
public OrganizationProfileMapping updateMapping(String providerId,OrganizationProfileMappingInput input){return updateMapping(providerId,input,RequestOptions.defaults());}
public CompletableFuture<OrganizationProfileMapping> updateMappingAsync(String providerId,OrganizationProfileMappingInput input,RequestOptions options){Objects.requireNonNull(options);Objects.requireNonNull(input);return transport.jsonAsync("PUT",prefix+"/organization/profile-mappings/"+Transport.id(providerId),input,options,transport.type(OrganizationProfileMapping.class));}
public CompletableFuture<OrganizationProfileMapping> updateMappingAsync(String providerId,OrganizationProfileMappingInput input){return updateMappingAsync(providerId,input,RequestOptions.defaults());}
}
